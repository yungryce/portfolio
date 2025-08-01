import json
from linecache import cache
import logging
import os
import time
import azure.functions as func
import azure.durable_functions as df
from datetime import datetime
from fa_helpers import create_success_response, create_error_response, get_orchestration_status, trim_processed_repo

# Updated imports - use individual managers instead of GitHubClient
from github.github_api import GitHubAPI
from github.cache_client import GitHubCache
from github.github_file_manager import GitHubFileManager
from github.github_repo_manager import GitHubRepoManager

# AI imports
from ai.type_analyzer import FileTypeAnalyzer

# Configure logging
LOG_FILE_PATH = os.getenv("API_LOG_FILE", "api_function_app.log")
logger = logging.getLogger('portfolio.api')
logger.setLevel(logging.DEBUG)

# Remove all handlers associated with the logger object (avoid duplicate logs)
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

file_handler = logging.FileHandler(LOG_FILE_PATH, mode='a', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

app = df.DFApp(http_auth_level=func.AuthLevel.ANONYMOUS)
logger.info("Function app initialized")

def _get_github_managers(username=None):
    """Get GitHub managers initialized with proper dependencies."""
    github_token = os.getenv('GITHUB_TOKEN')
    
    # Initialize components in dependency order
    api = GitHubAPI(token=github_token, username=username)
    cache = GitHubCache(use_cache=True)
    file_manager = GitHubFileManager(api, cache)
    repo_manager = GitHubRepoManager(api, cache, file_manager, username=username)
    
    return api, cache, file_manager, repo_manager


@app.route(route="orchestrators/repo_context_orchestrator", methods=["POST"])
@app.durable_client_input(client_name="client")
async def http_start(req: func.HttpRequest, client) -> func.HttpResponse:
    """
    HTTP endpoint to trigger the repo_context_orchestrator Durable Function.
    """
    logger.info("Received request to start repo_context_orchestrator")
    try:
        # username = "req.get_json().get('username')"
        username = "yungryce"
        
        # Check if cache already exists
        _, cache, _, _ = _get_github_managers(username)
        cache_key = cache._generate_cache_key(f"repos_bundle_context_{username}")
        logger.info(f"Checking cache for user '{username}' with key: {cache_key}")
        cached_results = cache._get_from_cache(cache_key)
        
        if cached_results:
            logger.info(f"Cache exists for user '{username}', skipping orchestration")
            # Return a success response with cache info
            return create_success_response({
                "status": "cached",
                "message": "Using cached repository data",
                "timestamp": datetime.now().isoformat(),
                "cache_key": cache_key,
                "repos_count": len(cached_results) if isinstance(cached_results, list) else 0
            })

        # Start the orchestrator asynchronously
        instance_id = await client.start_new('repo_context_orchestrator', None, username)
        logger.info(f"Started repo_context_orchestrator for user '{username}', instance ID: {instance_id}")

        # Return a status-check response for the orchestration
        response = client.create_check_status_response(req, instance_id)
        logger.info(f"Check status response: {response.get_body().decode()}")
        return response
    except Exception as e:
        logger.error(f"Error starting repo_context_orchestrator: {str(e)}")
        return create_error_response(f"Failed to start orchestration: {str(e)}", 500)

@app.orchestration_trigger(context_name="context")
def repo_context_orchestrator(context):
    """
    Durable Functions orchestrator for parallel repository context retrieval.
    """
    username = context.get_input()
    repos_metadata = yield context.call_activity('get_repo_names_activity', username)
    tasks = []
    for repo_metadata in repos_metadata:
        tasks.append(context.call_activity('fetch_repo_context_bundle_activity', {
            'username': username,
            'repo_metadata': trim_processed_repo(repo_metadata)
        }))
    results = yield context.task_all(tasks)
    logger.info(f"Completed fetching repo context bundles for user '{len(results)} of type {type(results)}'")
    
    # --- Cache the full bundle ---
    try:
        _, cache, _, _ = _get_github_managers(username)
        cache_key = cache._generate_cache_key(f"repos_bundle_context_{username}")
        if results and isinstance(results, list) and len(results) > 0:
            cache._save_to_cache(cache_key, results, ttl=3600)
            logger.info(f"Cached full repo context bundle ({len(results)} repos) under key: {cache_key}")
        else:
            logger.warning(f"Not caching empty results: {results}")
    except Exception as e:
        logger.warning(f"Failed to cache repo context bundle: {str(e)}")
    # ----------------------------
    
    return results

@app.activity_trigger(input_name="activityContext")
def get_repo_names_activity(activityContext):
    """
    Activity function to fetch list of repository names for a user.
    """
    username = activityContext
    _, _, _, repo_manager = _get_github_managers(username)
    repos = repo_manager.get_all_repos_metadata(include_languages=True)
    return repos


@app.activity_trigger(input_name="activityContext")
def fetch_repo_context_bundle_activity(activityContext):
    """
    Activity function to fetch repository metadata, languages, .repo-context.json, and file types for a single repository.
    """
    input_data = activityContext
    username = input_data.get('username')
    repo_metadata = input_data.get('repo_metadata')
    repo_name = repo_metadata.get('name')

    # Initialize managers
    _, _, _, repo_manager = _get_github_managers(username)
    file_type_analyzer = FileTypeAnalyzer()

    # Fetch .repo-context.json
    repo_context = repo_manager.get_file_content(repo_name=repo_name, path='.repo-context.json', username=username)
    if repo_context and isinstance(repo_context, str):
        import json
        try:
            repo_context = json.loads(repo_context)
        except Exception:
            repo_context = {}

    # Fetch file types using AI Assistant logic
    file_types = repo_manager.get_all_file_types(repo_name, username=username)
    categorized_types = file_type_analyzer.analyze_repository_files(file_types)

    # Aggregate results
    result = {
        "name": repo_name,
        "metadata": repo_metadata,
        "repoContext": repo_context,
        "file_types": file_types,
        "categorized_types": categorized_types,
        "languages": repo_metadata.get("languages", {}) if repo_metadata else {}
    }
    return result

@app.route(route="ai", methods=["POST"])
def portfolio_query(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("=-=-Received portfolio query request=-=-")
    try:
        # Parse request body
        request_body = req.get_json()
        if not request_body or 'query' not in request_body:
            return create_error_response("Request body must contain 'query' field", 400)
        
        query = request_body['query']
        username = request_body.get('username', 'yungryce')
        instance_id = request_body.get('instance_id')
        status_query_url = request_body.get('status_query_url')
        
        # Initialize AI assistant with updated managers
        _, cache, _, _ = _get_github_managers(username)
        from ai.ai_assistant import AIAssistant
        ai_assistant = AIAssistant(username=username)
        
        # Try to get cached results first
        cache_key = cache._generate_cache_key(f"repos_bundle_context_{username}")
        cached_results = cache._get_from_cache(cache_key)
        logger.debug(f"Cached results for user '{username}': {cached_results is not None}")
        repo_context_results = None
        
        if cached_results:
            repo_context_results = cached_results
            logger.info(f"Using cached results for user '{username}'")
        elif instance_id:
            # Fetch orchestration results from Durable Functions status endpoint
            # This assumes you have a helper to fetch orchestration output by instance_id
            orchestration_status = get_orchestration_status(instance_id, status_query_url)
            if orchestration_status and orchestration_status.get("runtimeStatus") == "Completed":
                # Normalize orchestration output to flat repo dicts
                repo_context_results = orchestration_status.get("output", [])
                cache._save_to_cache(cache_key, repo_context_results, ttl=3600)
                logger.info(f"Cached orchestration results under key: {cache_key}")
            else:
                return create_error_response("Orchestration not completed or results unavailable", 202)
        else:
            return create_error_response("No repo context results available. Provide instance_id or wait for orchestration.", 400)
        
        # Process the query
        response = ai_assistant.process_query_results(query, repo_context_results)
        
        return create_success_response(response)
    except Exception as e:
        logger.error(f"Error processing portfolio query: {str(e)}")
        return create_error_response(f"Failed to process query: {str(e)}", 500)

@app.route(route="github/repos/{username}", methods=["GET"])
def get_user_repos(req: func.HttpRequest) -> func.HttpResponse:
    try:
        username = req.route_params.get('username')
        if not username:
            return create_error_response("Username is required", 400)
        
        # Use repo manager directly
        _, _, _, repo_manager = _get_github_managers(username)
        repos = repo_manager.get_all_repos_metadata(username=username, include_languages=True)
        
        return create_success_response(repos)
    except Exception as e:
        logger.error(f"Error fetching repositories for {username}: {str(e)}")
        return create_error_response(f"Failed to fetch repositories: {str(e)}", 500)

@app.route(route="github/repos/{username}/{repo}", methods=["GET"])
def get_single_repo(req: func.HttpRequest) -> func.HttpResponse:
    try:
        username = req.route_params.get('username')
        repo = req.route_params.get('repo')
        
        if not username or not repo:
            return create_error_response("Username and repository name are required", 400)
        
        # Use repo manager directly
        _, _, _, repo_manager = _get_github_managers(username)
        repo_data = repo_manager.get_repo_metadata(username=username, repo=repo, include_languages=True)
        
        if not repo_data:
            return create_error_response(f"Repository {username}/{repo} not found", 404)
        
        return create_success_response(repo_data)
    except Exception as e:
        logger.error(f"Error fetching repository {username}/{repo}: {str(e)}")
        return create_error_response(f"Failed to fetch repository: {str(e)}", 500)

@app.route(route="github/repos/{username}/{repo}/files", methods=["GET"])
def get_repo_files(req: func.HttpRequest) -> func.HttpResponse:
    try:
        username = req.route_params.get('username')
        repo = req.route_params.get('repo')
        path = req.params.get('path', '')
        
        if not username or not repo:
            return create_error_response("Username and repository name are required", 400)
        
        # Use file manager directly
        _, _, file_manager, _ = _get_github_managers(username)
        files = file_manager.get_file_content(username=username, repo=repo, path=path)
        
        return create_success_response(files)
    except Exception as e:
        logger.error(f"Error fetching files for {username}/{repo}: {str(e)}")
        return create_error_response(f"Failed to fetch files: {str(e)}", 500)

@app.route(route="github/repos/{username}/with-context", methods=["GET"])
def get_user_repos_with_context(req: func.HttpRequest) -> func.HttpResponse:
    try:
        username = req.route_params.get('username')
        if not username:
            return create_error_response("Username is required", 400)
        
        # Use repo manager directly
        _, _, _, repo_manager = _get_github_managers(username)
        repos = repo_manager.get_all_repos_with_context(username=username, include_languages=True)
        
        return create_success_response(repos)
    except Exception as e:
        logger.error(f"Error fetching repositories with context for {username}: {str(e)}")
        return create_error_response(f"Failed to fetch repositories with context: {str(e)}", 500)

@app.timer_trigger(schedule="0 0 0 * * *", arg_name="myTimer", run_on_startup=False,
                   use_monitor=True) 
def cache_cleanup_timer(myTimer: func.TimerRequest) -> None:
    """
    Timer trigger that runs every hour to clean up expired cache blobs.
    Schedule: "0 0 * * * *" means at minute 0 of every hour.
    """
    logger.info('Cache cleanup timer triggered')
    
    if myTimer.past_due:
        logger.warning('Cache cleanup timer is running late')
    
    try:
        # Get GitHub token
        github_token = os.getenv('GITHUB_TOKEN')
        username = 'yungryce'
        
        if not github_token:
            logger.error('GitHub token not configured, skipping cache cleanup')
            return
        
        # Initialize managers
        _, cache, _, _ = _get_github_managers(username)
        
        # Get cache statistics before cleanup
        stats_before = cache.get_cache_statistics()
        logger.info(f"Cache stats before cleanup: {stats_before}")
        
        # Perform cache cleanup
        cleanup_results = cache.cleanup_expired_cache(
            batch_size=100,
            dry_run=False  # Set to True for testing
        )
        
        # Get cache statistics after cleanup
        stats_after = cache.get_cache_statistics()
        
        # Log cleanup results
        logger.info(f"Cache cleanup completed: {cleanup_results}")
        logger.info(f"Cache stats after cleanup: {stats_after}")
        
        # Log summary
        if cleanup_results['status'] == 'completed':
            logger.info(f"Successfully cleaned up {cleanup_results['deleted_count']} expired cache entries")
            
            # Log space savings
            if 'total_size_mb' in stats_before and 'total_size_mb' in stats_after:
                space_saved = stats_before['total_size_mb'] - stats_after['total_size_mb']
                if space_saved > 0:
                    logger.info(f"Cache cleanup freed {space_saved:.2f} MB of storage")
        else:
            logger.warning(f"Cache cleanup failed or skipped: {cleanup_results}")
            
    except Exception as e:
        logger.error(f"Cache cleanup timer failed: {str(e)}", exc_info=True)

@app.route(route="github/cache/cleanup", methods=["POST"])
def cleanup_cache(req: func.HttpRequest) -> func.HttpResponse:
    try:
        # Parse request body for cleanup options
        body = req.get_json() or {}
        dry_run = body.get('dry_run', False)
        batch_size = body.get('batch_size', 100)
        
        # Use cache manager directly
        _, cache, _, _ = _get_github_managers()
        result = cache.cleanup_expired_cache(batch_size=batch_size, dry_run=dry_run)
        
        return create_success_response(result)
    except Exception as e:
        logger.error(f"Error during cache cleanup: {str(e)}")
        return create_error_response(f"Cache cleanup failed: {str(e)}", 500)

@app.route(route="github/cache/stats", methods=["GET"])
def get_cache_stats(req: func.HttpRequest) -> func.HttpResponse:
    try:
        # Use cache manager directly
        _, cache, _, _ = _get_github_managers()
        stats = cache.get_cache_statistics()
        
        return create_success_response(stats)
    except Exception as e:
        logger.error(f"Error fetching cache statistics: {str(e)}")
        return create_error_response(f"Failed to fetch cache statistics: {str(e)}", 500)


@app.route(route="repository/{repo}/difficulty", auth_level=func.AuthLevel.ANONYMOUS, methods=["GET"])
def get_repository_difficulty(req: func.HttpRequest) -> func.HttpResponse:
    """Get difficulty rating for a specific repository"""
    logger.info('Processing repository difficulty request')
    
    try:
        repo_name = req.route_params.get('repo')
        if not repo_name:
            return create_error_response("Missing repository name in URL path", 400)
        # Get GitHub token
        github_token = os.getenv('GITHUB_TOKEN')
        username = 'yungryce'
        
        if not github_token:
            return create_error_response("GitHub token not configured", 500)
        
        # Initialize managers
        _, _, _, repo_manager = _get_github_managers(username)
        
        # Create AI Assistant with repo manager
        from ai.ai_assistant import AIAssistant
        ai_assistant = AIAssistant(username=username, repo_manager=repo_manager)
        
        # Get repository with context
        repos_with_context = repo_manager.get_all_repos_with_context(username)
        
        # Find the specific repository
        target_repo = None
        for repo in repos_with_context:
            if repo.get('name') == repo_name:
                target_repo = repo
                break
        
        if not target_repo:
            return create_error_response(f"Repository '{repo_name}' not found", 404)
        
        # Process language data first for best analysis
        from ai.helpers import process_language_data
        processed_repo = process_language_data(target_repo)
        
        # Calculate difficulty with enhanced scoring
        difficulty_data = ai_assistant.calculate_difficulty_score(processed_repo)
        
        # Extract key repository metrics for context
        primary_language = processed_repo.get('language', 'Unknown')
        languages = list(processed_repo.get('languages', {}).keys())[:5]  # Top 5 languages
        
        # Get topics and technologies for context
        topics = processed_repo.get('topics', [])
        tech_stack = processed_repo.get('repoContext', {}).get('tech_stack', {})
        primary_techs = tech_stack.get('primary', []) if tech_stack else []
        
        result = {
            "repository": repo_name,
            "difficulty_analysis": difficulty_data,
            "context": {
                "primary_language": primary_language,
                "languages": languages,
                "topics": topics,
                "primary_technologies": primary_techs
            },
            "metadata": {
                "analyzed_at": datetime.now().isoformat(),
                "analysis_version": "1.0"
            }
        }
        
        return create_success_response(result)
        
    except Exception as e:
        logger.error(f"Error calculating repository difficulty: {str(e)}", exc_info=True)
        return create_error_response(f"Internal server error: {str(e)}", 500)



# Add a health check endpoint
@app.route(route="health", auth_level=func.AuthLevel.ANONYMOUS)
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Enhanced health check endpoint with cache status"""
    logger.info('Processing API health check')
    
    # Perform basic GitHub connectivity test
    github_token = os.getenv('GITHUB_TOKEN')
    if github_token:
        try:
            # Initialize managers
            api, cache, _, _ = _get_github_managers('yungryce')
            
            # Test GitHub API connectivity
            rate_limit = api.make_request('GET', 'rate_limit')
            github_status = "connected" if rate_limit else "error"
            
            # Get cache statistics
            cache_stats = cache.get_cache_statistics()
            
        except Exception as e:
            logger.error(f"GitHub connectivity test failed: {str(e)}")
            github_status = f"error: {str(e)}"
            cache_stats = {"status": "error", "error": str(e)}
    else:
        github_status = "unconfigured"
        cache_stats = {"status": "unconfigured"}
    
    # Check GROQ API key
    groq_api_key = os.getenv('GROQ_API_KEY')
    groq_status = "configured" if groq_api_key else "unconfigured"
    
    # Check Azure Storage
    azure_storage = os.getenv('AzureWebJobsStorage')
    storage_status = "configured" if azure_storage else "unconfigured"
    
    health_data = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "environment": {
            "github_api": github_status,
            "groq_api": groq_status,
            "azure_storage": storage_status
        },
        "cache": cache_stats
    }
    
    return create_success_response(health_data, cache_control="no-cache")