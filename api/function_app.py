import json
import logging
import os
import azure.functions as func
from datetime import datetime

# Import the GitHub client
from github_client import GitHubClient

# Import AI assistant functions
from ai_assistant import query_ai_assistant

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


@app.route(route="portfolio/query", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST", "OPTIONS"])
def portfolio_query(req: func.HttpRequest) -> func.HttpResponse:
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
        username = 'yungryce'  # Your GitHub username
        
        if not github_token:
            logger.error('GitHub token not configured in environment variables')
            return create_error_response("GitHub token not configured", 500)
        
        # Create GitHub client
        gh_client = GitHubClient(token=github_token, username=username)
        
        # Try to get processed repos with graceful fallback
        try:
            logger.info("Retrieving processed repositories")
            filtered_repos = gh_client.get_processed_repos(username)
            logger.info(f"Successfully retrieved {len(filtered_repos)} repositories")
        except Exception as e:
            logger.error(f"Repository retrieval failed: {str(e)}", exc_info=True)
            if "Failed to resolve" in str(e) or "DNS resolution failure" in str(e):
                # Network error - check if we have any cached repos
                cache_key = f"processed_repos_{username}"
                cached_repos = gh_client._get_from_cache(cache_key)
                
                if cached_repos:
                    logger.info(f"Using {len(cached_repos)} cached repositories despite network error")
                    filtered_repos = cached_repos
                else:
                    return create_error_response(
                        "Network connectivity issue accessing GitHub API",
                        503,
                        "The server is having trouble connecting to GitHub. Please try again later."
                    )
            else:
                # Other error
                return handle_github_error(e, logger)
        
        # Get AI response using the blueprint function
        try:
            logger.info("Querying AI assistant with repository data")
            ai_response = query_ai_assistant(query, filtered_repos)
            logger.info(f"AI assistant generated a response of {len(ai_response)} chars")
        except Exception as e:
            logger.error(f"AI query failed: {str(e)}", exc_info=True)
            return create_error_response(f"AI processing error: {str(e)}", 500)
        
        # Return the AI response using helper
        result = {"response": ai_response}
        logger.info("Portfolio query processed successfully")
        return create_success_response(result)
            
    except Exception as e:
        logger.error(f"Error processing portfolio query: {str(e)}", exc_info=True)
        return create_error_response(f"Internal server error: {str(e)}", 500)


# Add a health check endpoint
@app.route(route="health", auth_level=func.AuthLevel.ANONYMOUS)
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Simple endpoint to check API health"""
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
        except Exception as e:
            logger.error(f"GitHub connectivity test failed: {str(e)}")
            github_status = f"error: {str(e)}"
    else:
        github_status = "unconfigured"
    
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
        }
    }
    
    return create_success_response(health_data, cache_control="no-cache")

