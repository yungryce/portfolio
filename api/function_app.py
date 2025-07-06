import json
import logging
import os
import azure.functions as func
from datetime import datetime

# Import the GitHub client
from github_client import GitHubClient

# Import AI assistant functions and class
from ai_assistant import (
    filter_repositories_with_terms,
    query_ai_assistant_with_context as ai_assistant_context,
    extract_search_terms,
    AIAssistant  # Add the class import
)

# Import helper functions
from helpers import (
    format_file_response,
    handle_github_error,
    validate_github_params,
    create_error_response,
    create_success_response
)

# Configure logging
logger = logging.getLogger('portfolio.api')
logger.setLevel(logging.INFO)

app = func.FunctionApp()


@app.route(route="github/repos/{username}/{repo}", auth_level=func.AuthLevel.ANONYMOUS)
def get_repository_metadata(req: func.HttpRequest) -> func.HttpResponse:
    # Get parameters from route
    username = req.route_params.get('username')
    repo = req.route_params.get('repo')
    
    logger.info(f"Processing request for specific GitHub repo: {username}/{repo}")
    
    # Validate parameters using helper
    validation_error = validate_github_params(username, repo)
    if validation_error:
        return validation_error
    
    # Get token from environment
    github_token = os.getenv('GITHUB_TOKEN')
    
    if not github_token:
        logger.error('GitHub token not configured in environment variables')
        return create_error_response("GitHub token not configured", 500)
    
    # Create GitHub client
    gh_client = GitHubClient(token=github_token, username=username)
    
    try:
        # Get repository details
        repo_details = gh_client.get_repo_metadata(username, repo)
        
        if not repo_details:
            logger.warning(f"Repository not found: {username}/{repo}")
            return create_error_response("Repository not found", 404)
        
        return create_success_response(repo_details)
        
    except Exception as e:
        logger.error(f"Error fetching repository details: {str(e)}", exc_info=True)
        return handle_github_error(e, logger)


@app.route(route="github/repos", auth_level=func.AuthLevel.ANONYMOUS)
def get_all_repositories_metadata(req: func.HttpRequest) -> func.HttpResponse:
    logger.info('Processing request for GitHub repos listing')
    
    # Get token from environment
    github_token = os.getenv('GITHUB_TOKEN')
    username = 'yungryce'  # Your GitHub username
    
    if not github_token:
        logger.error('GitHub token not configured in environment variables')
        return create_error_response("GitHub token not configured", 500)
    
    # Create GitHub client
    gh_client = GitHubClient(token=github_token, username=username)
    
    try:
        # Get the repositories
        all_repos = gh_client.get_all_repos_metadata(username)
        top_repos = all_repos[:10]  # Take only the first 10
        
        logger.info(f"Successfully retrieved {len(top_repos)} repositories")
        return create_success_response(top_repos)
        
    except Exception as e:
        logger.error(f"Error fetching GitHub repositories: {str(e)}", exc_info=True)
        return handle_github_error(e, logger)


@app.route(route="github/repos/{username}/{repo}/contents/{path:regex(.+)}", auth_level=func.AuthLevel.ANONYMOUS)
def get_repository_file_content(req: func.HttpRequest) -> func.HttpResponse:
    username = req.route_params.get('username')
    repo = req.route_params.get('repo')
    file_path = req.route_params.get('path')
    
    logger.info(f"Processing file request: {username}/{repo}/{file_path}")
    
    # Validate parameters using helper
    validation_error = validate_github_params(username, repo, file_path)
    if validation_error:
        return validation_error
        
    # Get GitHub token
    github_token = os.getenv('GITHUB_TOKEN')
    if not github_token:
        logger.error("GitHub token not configured")
        return create_error_response("GitHub token not configured", 500)
    
    try:
        # Create GitHub client with optimized caching
        gh_client = GitHubClient(token=github_token, username=username)
        
        # Fetch file content (returns raw content or dict for directories)
        file_content = gh_client.get_file_content(username, repo, file_path)
        logger.debug(f"Fetched file content for {file_path} in {username}/{repo}")
        
        if not file_content:
            logger.info(f"File not found: {username}/{repo}/{file_path}")
            return create_error_response(
                f"File '{file_path}' not found in repository '{username}/{repo}'", 
                404
            )
        
        # Handle directory response (dict of container files)
        if isinstance(file_content, dict):
            logger.info(f"Returning directory listing with {len(file_content)} files")
            return create_success_response(file_content)
        
        # Handle single file content - use helper function with logger context
        logger.debug(f"Formatting single file response for {file_path}")
        return format_file_response(file_content, file_path, logger)
        
    except Exception as e:
        logger.error(f"Error fetching file {file_path} from {username}/{repo}: {str(e)}", exc_info=True)
        return handle_github_error(e, logger)


@app.route(route="ai", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST", "OPTIONS"])
def ai_query(req: func.HttpRequest) -> func.HttpResponse:
    logger.info('Processing portfolio query with AI assistance')
    
    try:
        # Parse request body
        req_body = req.get_json()
        query = req_body.get('query')
        
        if not query:
            logger.warning('Portfolio query request missing query parameter')
            return create_error_response("Missing query parameter", 400)
        
        logger.info(f"Portfolio query received: {query[:100]}...")
        
        # Get GitHub token from environment
        github_token = os.getenv('GITHUB_TOKEN')
        username = 'yungryce'
        
        if not github_token:
            logger.error('GitHub token not configured in environment variables')
            return create_error_response("GitHub token not configured", 500)
        
        # Create GitHub client
        gh_client = GitHubClient(token=github_token, username=username)
        
        # Get all repositories with enhanced caching
        try:
            logger.info("Retrieving all repositories for search")
            all_repos = gh_client.get_all_repos_with_context(username)
            logger.info(f"Successfully retrieved {len(all_repos)} repositories")
        except Exception as e:
            logger.error(f"Repository retrieval failed: {str(e)}", exc_info=True)
            return handle_github_error(e, logger)
        
        # Stage 1: Extract search terms ONCE from all repositories
        try:
            logger.info("Extracting search terms from query and repositories")
            search_terms = extract_search_terms(query.lower(), all_repos)
            logger.info(f"Extracted search terms: {dict(search_terms)}")
        except Exception as e:
            logger.error(f"Search term extraction failed: {str(e)}", exc_info=True)
            search_terms = {'tech': [], 'skills': [], 'components': [], 'project': [], 'general': []}
        
        # Stage 2: Filter repositories using pre-extracted search terms
        try:
            logger.info("Filtering repositories based on query relevance")
            relevant_repos = filter_repositories_with_terms(query, all_repos, search_terms)
            logger.info(f"Found {len(relevant_repos)} relevant repositories")
        except Exception as e:
            logger.error(f"Repository filtering failed: {str(e)}", exc_info=True)
            # Fallback to all repos if filtering fails
            relevant_repos = all_repos
        
        # Stage 3: Generate AI response with filtered context
        try:
            logger.info("Querying AI assistant with filtered repository data")
            ai_response = ai_assistant_context(query, relevant_repos)
            logger.info(f"AI assistant generated a response of {len(ai_response)} chars")
        except Exception as e:
            logger.error(f"AI query failed: {str(e)}", exc_info=True)
            return create_error_response(f"AI processing error: {str(e)}", 500)
        
        # Return the AI response with enhanced metadata
        result = {
            "response": ai_response,
            "metadata": {
                "total_repos_searched": len(all_repos),
                "relevant_repos_found": len(relevant_repos),
                "query_processed": query[:100] + "..." if len(query) > 100 else query,
                "search_terms_found": {
                    "tech": len(search_terms.get('tech', [])),
                    "skills": len(search_terms.get('skills', [])),
                    "components": len(search_terms.get('components', [])),
                    "project": len(search_terms.get('project', [])),
                    "general": len(search_terms.get('general', []))
                },
                "repositories_analyzed": [repo.get('name', 'Unknown') for repo in relevant_repos[:5]]
            }
        }
        
        logger.info("Portfolio query processed successfully")
        return create_success_response(result)
            
    except Exception as e:
        logger.error(f"Error processing portfolio query: {str(e)}", exc_info=True)
        return create_error_response(f"Internal server error: {str(e)}", 500)



@app.route(route="repository-difficulty", auth_level=func.AuthLevel.ANONYMOUS, methods=["GET"])
def get_repository_difficulty(req: func.HttpRequest) -> func.HttpResponse:
    """Get difficulty rating for a specific repository"""
    logger.info('Processing repository difficulty request')
    
    try:
        repo_name = req.params.get('repo')
        if not repo_name:
            return create_error_response("Missing 'repo' parameter", 400)
        
        # Get GitHub token
        github_token = os.getenv('GITHUB_TOKEN')
        username = 'yungryce'
        
        if not github_token:
            return create_error_response("GitHub token not configured", 500)
        
        # Create AI Assistant
        ai_assistant = AIAssistant(github_token=github_token, username=username)
        
        # Get repository with context
        gh_client = GitHubClient(token=github_token, username=username)
        repos_with_context = gh_client.get_all_repos_with_context(username)
        
        # Find the specific repository
        target_repo = None
        for repo in repos_with_context:
            if repo.get('name') == repo_name:
                target_repo = repo
                break
        
        if not target_repo:
            return create_error_response(f"Repository '{repo_name}' not found", 404)
        
        # Calculate difficulty
        difficulty_data = ai_assistant.calculate_difficulty_score(target_repo)
        
        result = {
            "repository": repo_name,
            "difficulty_analysis": difficulty_data,
            "metadata": {
                "analyzed_at": datetime.now().isoformat(),
                "analysis_version": "1.0"
            }
        }
        
        return create_success_response(result)
        
    except Exception as e:
        logger.error(f"Error calculating repository difficulty: {str(e)}", exc_info=True)
        return create_error_response(f"Internal server error: {str(e)}", 500)

# Add this timer trigger function

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
        
        # Create GitHub client
        gh_client = GitHubClient(token=github_token, username=username)
        
        # Get cache statistics before cleanup
        stats_before = gh_client.get_cache_statistics()
        logger.info(f"Cache stats before cleanup: {stats_before}")
        
        # Perform cache cleanup
        cleanup_results = gh_client.cleanup_expired_cache(
            batch_size=100,
            dry_run=False  # Set to True for testing
        )
        
        # Get cache statistics after cleanup
        stats_after = gh_client.get_cache_statistics()
        
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


@app.route(route="cache/stats", auth_level=func.AuthLevel.ANONYMOUS, methods=["GET"])
def get_cache_stats(req: func.HttpRequest) -> func.HttpResponse:
    """Get current cache statistics"""
    logger.info('Processing cache statistics request')
    
    try:
        # Get GitHub token
        github_token = os.getenv('GITHUB_TOKEN')
        username = 'yungryce'
        
        if not github_token:
            return create_error_response("GitHub token not configured", 500)
        
        # Create GitHub client
        gh_client = GitHubClient(token=github_token, username=username)
        
        # Get cache statistics
        stats = gh_client.get_cache_statistics()
        
        return create_success_response(stats)
        
    except Exception as e:
        logger.error(f"Error getting cache statistics: {str(e)}", exc_info=True)
        return create_error_response(f"Internal server error: {str(e)}", 500)


@app.route(route="cache/cleanup", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST"])
def manual_cache_cleanup(req: func.HttpRequest) -> func.HttpResponse:
    """Manually trigger cache cleanup"""
    logger.info('Processing manual cache cleanup request')
    
    try:
        # Parse request parameters
        req_body = req.get_json() or {}
        dry_run = req_body.get('dry_run', False)
        batch_size = req_body.get('batch_size', 100)
        
        # Get GitHub token
        github_token = os.getenv('GITHUB_TOKEN')
        username = 'yungryce'
        
        if not github_token:
            return create_error_response("GitHub token not configured", 500)
        
        # Create GitHub client
        gh_client = GitHubClient(token=github_token, username=username)
        
        # Get cache statistics before cleanup
        stats_before = gh_client.get_cache_statistics()
        
        # Perform cache cleanup
        cleanup_results = gh_client.cleanup_expired_cache(
            batch_size=batch_size,
            dry_run=dry_run
        )
        
        # Get cache statistics after cleanup
        stats_after = gh_client.get_cache_statistics()
        
        # Return comprehensive results
        result = {
            "cleanup_results": cleanup_results,
            "stats_before": stats_before,
            "stats_after": stats_after,
            "space_saved_mb": 0
        }
        
        # Calculate space savings
        if 'total_size_mb' in stats_before and 'total_size_mb' in stats_after:
            result["space_saved_mb"] = round(
                stats_before['total_size_mb'] - stats_after['total_size_mb'], 2
            )
        
        logger.info(f"Manual cache cleanup completed: {cleanup_results}")
        return create_success_response(result)
        
    except Exception as e:
        logger.error(f"Error during manual cache cleanup: {str(e)}", exc_info=True)
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
            # Create GitHub client with short cache TTL
            gh_client = GitHubClient(token=github_token, username='yungryce')
            gh_client.cache_ttl = 60  # 1 minute cache
            
            # Test GitHub API connectivity
            rate_limit = gh_client.make_request('GET', 'rate_limit')
            github_status = "connected" if rate_limit else "error"
            
            # Get cache statistics
            cache_stats = gh_client.get_cache_statistics()
            
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
