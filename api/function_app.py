import json
import logging
import os
import time
import azure.functions as func
import azure.durable_functions as df
from datetime import datetime
from fa_helpers import create_success_response, create_error_response, get_orchestration_status, trim_processed_repo

# Updated imports - use individual managers instead of GitHubClient
from github.github_api import GitHubAPI
from github.cache_manager import cache_manager
from github.github_repo_manager import GitHubRepoManager
from github.fingerprint_manager import FingerprintManager

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


# Fix initialization of GitHubFileManager and GitHubRepoManager
def _get_github_managers(username=None):
    """Get GitHub managers initialized with proper dependencies."""
    github_token = os.getenv('GITHUB_TOKEN')

    # Initialize components in dependency order
    api = GitHubAPI(token=github_token, username=username)
    repo_manager = GitHubRepoManager(api, username=username)

    return repo_manager


@app.route(route="orchestrators/repo_context_orchestrator", methods=["POST"])
@app.durable_client_input(client_name="client")
async def http_start(req: func.HttpRequest, client) -> func.HttpResponse:
    """
    HTTP endpoint to trigger the repo_context_orchestrator Durable Function.
    Enhanced with smarter cache checking and force refresh option.
    """
    logger.info("Received request to start repo_context_orchestrator")
    try:
        # Parse request body
        request_body = req.get_json() or {}
        username = request_body.get('username', 'yungryce')
        force_refresh = request_body.get('force_refresh', False)

        # Check cache status
        bundle_cache_key = cache_manager.generate_cache_key(kind='bundle', username=username)
        logger.info(f"Checking cache for user '{username}' with key: {bundle_cache_key}")

        if not force_refresh:
            cache_entry = cache_manager.get(bundle_cache_key)
            if cache_entry['status'] == 'valid' and cache_entry['data']:
                logger.info(f"Cache exists for user '{username}', cache info: {len(cache_entry['data'])} repositories")

                # Get current repository list and calculate fingerprints
                repo_manager = _get_github_managers(username)
                current_repos = repo_manager.get_all_repos_metadata(username=username, include_languages=False)

                current_fingerprints = {
                    repo.get('name'): FingerprintManager.generate_metadata_fingerprint(repo)
                    for repo in current_repos if repo.get('name')
                }
                
                # Generate a current bundle fingerprint
                current_repo_fingerprints = list(current_fingerprints.values())
                current_bundle_fingerprint = FingerprintManager.generate_bundle_fingerprint(current_repo_fingerprints)
                
                # Compare with cached bundle fingerprint
                cached_bundle_fingerprint = cache_entry.get('fingerprint')
                
                if cached_bundle_fingerprint and cached_bundle_fingerprint == current_bundle_fingerprint:
                    logger.info("Combined bundle fingerprints match")
                    # Return cached response with bundle fingerprint
                    return create_success_response({
                        "status": "cached",
                        "message": "Using cached repository data (fingerprint match)",
                        "timestamp": datetime.now().isoformat(),
                        "cache_key": bundle_cache_key,
                        "repos_count": len(cache_entry['data']) if isinstance(cache_entry['data'], list) else 0,
                        "bundle_fingerprint": cached_bundle_fingerprint,
                        "cache_info": {
                            "last_modified": cache_entry.get('last_modified'),
                            "size_bytes": cache_entry.get('size_bytes'),
                            "no_expiry": cache_entry.get('no_expiry', False)
                        }
                    })
            else:
                logger.info(f"No valid cache found for user '{username}', proceeding with orchestration")
        else:
            logger.info(f"Force refresh requested for user '{username}', ignoring cache")

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
    Only processes repositories with stale or missing cache entries.
    """
    username = context.get_input()

    # Get repositories that need processing (stale or missing from cache)
    repos_data = yield context.call_activity('get_stale_repos_activity', username)

    if not repos_data['stale_repos'] and repos_data['cached_bundle']:
        logger.info(f"No stale repositories found for user '{username}', returning cached bundle")
        logger.info(f"Cached bundle contains {len(repos_data['cached_bundle'])} repositories")
        return repos_data['cached_bundle']

    logger.info(f"Processing {len(repos_data['stale_repos'])} stale repositories for user '{username}'")

    # Process only stale repositories
    tasks = []
    for repo_metadata in repos_data['stale_repos']:
        tasks.append(context.call_activity('fetch_repo_context_bundle_activity', {
            'username': username,
            'repo_metadata': trim_processed_repo(repo_metadata)
        }))

    # Get results for stale repositories
    stale_results = yield context.task_all(tasks)

    # Merge fresh and cached data
    merged_results = yield context.call_activity('merge_repo_results_activity', {
        'username': username,
        'fresh_results': stale_results,
        'cached_bundle': repos_data['cached_bundle']
    })

    logger.info(f"Completed repo context orchestration for user '{username}': "
                f"{len(stale_results)} processed, {len(merged_results)} total repositories")

    return merged_results

@app.activity_trigger(input_name="activityContext")
def get_stale_repos_activity(activityContext):
    """
    Activity function to identify repositories that need processing.
    Uses fingerprinting to detect changes instead of relying solely on TTL.
    Returns both stale repositories and existing cached bundle.
    """
    username = activityContext
    repo_manager = _get_github_managers(username)

    # Fetch cached bundle
    bundle_cache_key = cache_manager.generate_cache_key(kind='bundle', username=username)
    cached_bundle = cache_manager.get(bundle_cache_key)
    # logger.info(f"Bundle cache status for '{username}': {cached_bundle.get('status')}")

    # Fetch current repository metadata
    all_repos_metadata = repo_manager.get_all_repos_metadata(username=username, include_languages=True)

    # Calculate fingerprints for current repositories
    current_fingerprints = {
        repo.get('name'): FingerprintManager.generate_metadata_fingerprint(repo)
        for repo in all_repos_metadata if repo.get('name')
    }

    # Extract fingerprints from cached bundle
    cached_fingerprints = {
        repo.get('metadata', {}).get('name'): repo.get('fingerprint')
        for repo in (cached_bundle.get('data') or [])
        if repo.get('metadata', {}).get('name')
    }

    # Identify stale and valid repositories
    stale_repos = []
    valid_repos = []
    for repo_metadata in all_repos_metadata:
        repo_name = repo_metadata.get('name')
        if not repo_name:
            continue

        current_fingerprint = current_fingerprints.get(repo_name)
        cached_fingerprint = cached_fingerprints.get(repo_name)

        if current_fingerprint != cached_fingerprint:
            if cached_fingerprint is None:
                logger.info(f"Repo '{repo_name}' is stale due to missing cache entry.")
            else:
                logger.warning(
                    f"Fingerprint mismatch for repo '{repo_name}': "
                    f"current='{current_fingerprint}', cached='{cached_fingerprint}'"
                )
            stale_repos.append(repo_metadata)
        else:
            valid_repos.append(repo_metadata)

    # Hydrate valid repositories from per-repo cache
    hydrated_valid_repos = []
    for repo_metadata in valid_repos:
        repo_name = repo_metadata.get('name')
        repo_cache_key = cache_manager.generate_cache_key(kind='repo', username=username, repo=repo_name)
        cached_repo = cache_manager.get(repo_cache_key)
        if cached_repo and isinstance(cached_repo.get('data'), dict):
            hydrated_valid_repos.append(cached_repo['data'])
        else:
            logger.warning(f"Repo '{repo_name}' missing or invalid in per-repo cache, reclassifying as stale")
            stale_repos.append(repo_metadata)

    # Return results
    logger.info(f"Found {len(stale_repos)} stale and {len(hydrated_valid_repos)} valid repositories for user '{username}'")
    return {
        'stale_repos': stale_repos,
        'cached_bundle': hydrated_valid_repos
    }

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
    repo_manager = _get_github_managers(username)

    # Generate fingerprint for this repository
    fingerprint = FingerprintManager.generate_metadata_fingerprint(repo_metadata)

    # Fetch .repo-context.json
    repo_context = repo_manager.get_file_content(repo=repo_name, path='.repo-context.json', username=username)
    repo_context = json.loads(repo_context) if repo_context and isinstance(repo_context, str) else {}
    
    # Fetch README.md
    readme_content = repo_manager.get_file_content(repo=repo_name, path='README.md', username=username) or ""

    # Fetch SKILLS-INDEX.md
    skills_index_content = repo_manager.get_file_content(repo=repo_name, path='SKILLS-INDEX.md', username=username) or ""

    # Fetch ARCHITECTURE.md
    architecture_content = repo_manager.get_file_content(repo=repo_name, path='ARCHITECTURE.md', username=username) or ""

    # Analyze file types
    file_type_analyzer = FileTypeAnalyzer()
    file_types = repo_manager.get_all_file_types(repo_name, username)
    categorized_types = file_type_analyzer.analyze_repository_files(file_types)

    # Combine results
    result = {
        "name": repo_name,
        'metadata': repo_metadata,
        'repoContext': repo_context,
        'readme': readme_content,
        'skills_index': skills_index_content,
        'architecture': architecture_content,
        'file_types': file_types,
        "categorized_types": categorized_types,
        'fingerprint': fingerprint,
        "languages": repo_metadata.get("languages", {}) if repo_metadata else {},
        'has_documentation': bool(repo_context) and bool(readme_content)
    }

    # Save to cache
    repo_cache_key = cache_manager.generate_cache_key(kind='repo', username=username, repo=repo_name)
    cache_manager.save(repo_cache_key, result, ttl=None, fingerprint=fingerprint) # No TTL for repo context
    logger.info(f"Saved repository '{repo_name}' with fingerprint: {fingerprint}")

    return result

@app.activity_trigger(input_name="activityContext")
def merge_repo_results_activity(activityContext):
    """
    Activity function to merge fresh repository results with cached bundle.
    """
    input_data = activityContext
    username = input_data.get('username')
    fresh_results = input_data.get('fresh_results', [])
    cached_bundle = input_data.get('cached_bundle', [])

    # Create lookup for fresh results by repository name
    fresh_repo_lookup = {result.get('metadata', {}).get('name'): result
                         for result in fresh_results if result.get('metadata', {}).get('name')}

    # Start with cached bundle and update with fresh results
    merged_results = []
    processed_repo_names = set()

    # Update cached repos with fresh data where available
    for cached_repo in cached_bundle:
        repo_name = cached_repo.get('metadata', {}).get('name')
        if repo_name in fresh_repo_lookup:
            # Use fresh data
            merged_results.append(fresh_repo_lookup[repo_name])
            processed_repo_names.add(repo_name)
            logger.debug(f"Updated repository '{repo_name}' with fresh data")
        else:
            # Keep cached data
            merged_results.append(cached_repo)
            processed_repo_names.add(repo_name)

    # Add any new repositories that weren't in the cached bundle
    for fresh_repo in fresh_results:
        repo_name = fresh_repo.get('metadata', {}).get('name')
        if repo_name and repo_name not in processed_repo_names:
            merged_results.append(fresh_repo)
            logger.debug(f"Added new-merge repository '{repo_name}' to bundle")

    # Cache individual repository results
    for fresh_repo in fresh_results:
        repo_name = fresh_repo.get('metadata', {}).get('name')
        if repo_name:
            repo_cache_key = cache_manager.generate_cache_key(kind='repo', username=username, repo=repo_name)
            fingerprint = fresh_repo.get('fingerprint')
            cache_manager.save(repo_cache_key, fresh_repo, ttl=None, fingerprint=fingerprint)  # Use None for TTL

    # Cache the complete merged bundle which uses fingerprints
    bundle_cache_key = cache_manager.generate_cache_key(kind='bundle', username=username)
    if merged_results:
        repo_fingerprints = [repo.get('fingerprint', '') for repo in merged_results]
        bundle_fingerprint = FingerprintManager.generate_bundle_fingerprint(repo_fingerprints)
        
        cache_manager.save(bundle_cache_key, merged_results, ttl=None, fingerprint=bundle_fingerprint)
        logger.info(f"Cached merged bundle with {len(merged_results)} repositories under key: {bundle_cache_key}")
        logger.info(f"Bundle fingerprint: {bundle_fingerprint}")
    return merged_results

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
        from ai.ai_assistant import AIAssistant
        ai_assistant = AIAssistant(username=username)

        # Try to get cached results first
        cache_key = cache_manager.generate_cache_key(kind='bundle', username=username)
        cached_results = cache_manager.get(cache_key)
        logger.debug(f"Cached results for user '{username}': {cached_results is not None}")
        
        all_repos_bundle = None
        if cached_results and isinstance(cached_results.get('data'), list):
            all_repos_bundle = cached_results['data']
            logger.info(f"Using valid cached results for user '{username}'")

        if not all_repos_bundle and instance_id:
            orchestration_status = get_orchestration_status(instance_id, status_query_url)
            if orchestration_status and orchestration_status.get("runtimeStatus") == "Completed":
                all_repos_bundle = orchestration_status.get("output", [])
                cache_manager.save(cache_key, all_repos_bundle)
            else:
                return create_error_response("Orchestration not completed or results unavailable", 202)
        elif not all_repos_bundle:
            return create_error_response("No repo context results available. Provide instance_id or wait for orchestration.", 400)

        # Process the query
        response = ai_assistant.process_query_results(query, all_repos_bundle)

        return create_success_response(response)
    except Exception as e:
        logger.error(f"Error processing portfolio query: {str(e)}")
        return create_error_response(f"Failed to process query: {str(e)}", 500)

@app.route(route="github/repos/{username}", methods=["GET"])
def get_user_repos(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP endpoint to fetch all repositories for a user.
    """
    username = req.route_params.get('username')
    repo_manager = _get_github_managers(username)

    try:
        repos = repo_manager.get_all_repos_metadata(username=username, include_languages=True)
        return create_success_response({"repos": repos})
    except Exception as e:
        logger.error(f"Error fetching repositories for user '{username}': {str(e)}")
        return create_error_response(f"Failed to fetch repositories: {str(e)}", 500)

@app.route(route="github/repos/{username}/{repo}", methods=["GET"])
def get_single_repo(req: func.HttpRequest) -> func.HttpResponse:
    try:
        username = req.route_params.get('username')
        repo = req.route_params.get('repo')

        if not username or not repo:
            return create_error_response("Username and repository name are required", 400)

        # Use repo manager directly
        repo_manager = _get_github_managers(username)
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
        repo_manager = _get_github_managers(username)
        files = repo_manager.get_file_content(username=username, repo=repo, path=path)

        return create_success_response({"files": files})
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
        repo_manager = _get_github_managers(username)
        repos = repo_manager.get_all_repos_with_context(username=username, include_languages=True)

        return create_success_response(repos)
    except Exception as e:
        logger.error(f"Error fetching repositories with context for {username}: {str(e)}")
        return create_error_response(f"Failed to fetch repositories with context: {str(e)}", 500)

@app.timer_trigger(schedule="0 0 0 * * *", arg_name="myTimer", run_on_startup=False,
                   use_monitor=True) # Every hour
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

        # Get cache statistics before cleanup
        stats_before = cache_manager.get_cache_statistics()
        logger.info(f"Cache stats before cleanup: {stats_before}")

        # Perform cache cleanup
        cleanup_results = cache_manager.cleanup_expired_cache(
            batch_size=100,
            dry_run=False  # Set to True for testing
        )

        # Get cache statistics after cleanup
        stats_after = cache_manager.get_cache_statistics()

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
        result = cache_manager.cleanup_expired_cache(batch_size=batch_size, dry_run=dry_run)

        return create_success_response(result)
    except Exception as e:
        logger.error(f"Error during cache cleanup: {str(e)}")
        return create_error_response(f"Cache cleanup failed: {str(e)}", 500)

@app.route(route="github/cache/stats", methods=["GET"])
def get_cache_stats(req: func.HttpRequest) -> func.HttpResponse:
    try:
        # Use cache manager directly
        stats = cache_manager.get_cache_statistics()

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
        repo_manager = _get_github_managers(username)

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



# # Add a health check endpoint
# @app.route(route="health", auth_level=func.AuthLevel.ANONYMOUS)
# def health_check(req: func.HttpRequest) -> func.HttpResponse:
#     """Enhanced health check endpoint with cache status"""
#     logger.info('Processing API health check')

#     # Perform basic GitHub connectivity test
#     github_token = os.getenv('GITHUB_TOKEN')
#     if github_token:
#         try:
#             # Initialize managers
#             api, _, _ = _get_github_managers('yungryce')

#             # Test GitHub API connectivity
#             rate_limit = api.make_request('GET', 'rate_limit')
#             github_status = "connected" if rate_limit else "error"

#             # Get cache statistics
#             cache_stats = cache_manager.get_cache_statistics()

#         except Exception as e:
#             logger.error(f"GitHub connectivity test failed: {str(e)}")
#             github_status = f"error: {str(e)}"
#             cache_stats = {"status": "error", "error": str(e)}
#     else:
#         github_status = "unconfigured"
#         cache_stats = {"status": "unconfigured"}

#     # Check GROQ API key
#     groq_api_key = os.getenv('GROQ_API_KEY')
#     groq_status = "configured" if groq_api_key else "unconfigured"

#     # Check Azure Storage
#     azure_storage = os.getenv('AzureWebJobsStorage')
#     storage_status = "configured" if azure_storage else "unconfigured"

#     health_data = {
#         "status": "healthy",
#         "timestamp": datetime.now().isoformat(),
#         "environment": {
#             "github_api": github_status,
#             "groq_api": groq_status,
#             "azure_storage": storage_status
#         },
#         "cache": cache_stats
#     }

#     return create_success_response(health_data, cache_control="no-cache")