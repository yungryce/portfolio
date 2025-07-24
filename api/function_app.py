import json
import logging
import os
import time
import azure.functions as func
from datetime import datetime
from fa_helpers import create_success_response, create_error_response, validate_github_params

# Updated imports - use individual managers instead of GitHubClient
from github.github_api import GitHubAPI
from github.cache_client import GitHubCache
from github.github_file_manager import GitHubFileManager
from github.github_repo_manager import GitHubRepoManager

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

app = func.FunctionApp()
logger.info("Function app initialized")


def _get_github_managers(username=None):
    """Get GitHub managers initialized with proper dependencies."""
    github_token = os.getenv('GITHUB_TOKEN')
    
    # Initialize components in dependency order
    api = GitHubAPI(token=github_token, username=username)
    cache = GitHubCache(use_cache=True)
    file_manager = GitHubFileManager(api, cache)
    repo_manager = GitHubRepoManager(api, cache, file_manager)
    
    return api, cache, file_manager, repo_manager

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

@app.timer_trigger(schedule="0 0 * * * *", arg_name="myTimer", run_on_startup=False,
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

@app.route(route="ai", methods=["POST"])
def portfolio_query(req: func.HttpRequest) -> func.HttpResponse:
    try:
        # Parse request body
        request_body = req.get_json()
        if not request_body or 'query' not in request_body:
            return create_error_response("Request body must contain 'query' field", 400)
        
        query = request_body['query']
        username = request_body.get('username', 'yungryce')
        
        # Initialize AI assistant with updated managers
        _, _, _, repo_manager = _get_github_managers(username)
        from ai.ai_assistant import AIAssistant
        ai_assistant = AIAssistant(username=username, repo_manager=repo_manager)
        
        # Process the query
        response = ai_assistant.process_query(query)
        
        return create_success_response(response)
    except Exception as e:
        logger.error(f"Error processing portfolio query: {str(e)}")
        return create_error_response(f"Failed to process query: {str(e)}", 500)

@app.route(route="repository/{repo}/difficulty", auth_level=func.AuthLevel.ANONYMOUS, methods=["GET"])
def get_repository_difficulty(req: func.HttpRequest) -> func.HttpResponse:
    """Get difficulty rating for a specific repository"""
    logger.info('Processing repository difficulty request')
    
    try:
        repo_name = req.route_params.get('repo')
        if not repo_name:
            return create_error_response("Missing repository name in URL path", 400)
        l
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
        from ai.helpers_old import process_language_data
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