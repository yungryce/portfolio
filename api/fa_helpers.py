import json
import logging
import os
import azure.functions as func
from typing import Optional, Dict, List, Any
from datetime import datetime


logger = logging.getLogger('portfolio.api')

def create_success_response(data: dict, cache_control: str = "public, max-age=900") -> func.HttpResponse:
    """Create standardized success response with caching."""
    
    return func.HttpResponse(
        json.dumps(data, indent=2),
        status_code=200,
        mimetype="application/json",
        headers={
            "Cache-Control": cache_control,
            "Content-Type": "application/json; charset=utf-8"
        }
    )

def create_error_response(message: str, status_code: int = 500, details: str = None) -> func.HttpResponse:
    """Create standardized error response."""
    
    response_data = {"error": message}
    if details:
        response_data["details"] = details
    
    return func.HttpResponse(
        json.dumps(response_data),
        status_code=status_code,
        mimetype="application/json"
    )

def validate_github_params(username: str, repo: str, file_path: str = None) -> func.HttpResponse:
    """Validate GitHub API parameters and return error response if invalid."""
    
    if not username or not username.strip():
        return func.HttpResponse(
            json.dumps({"error": "Missing or invalid username parameter"}),
            status_code=400,
            mimetype="application/json"
        )
    
    if not repo or not repo.strip():
        return func.HttpResponse(
            json.dumps({"error": "Missing or invalid repository parameter"}),
            status_code=400,
            mimetype="application/json"
        )
    
    if file_path is not None and not file_path.strip():
        return func.HttpResponse(
            json.dumps({"error": "Missing or invalid file path parameter"}),
            status_code=400,
            mimetype="application/json"
        )
    
    return None  # No validation errors

def format_file_response(file_content: str, file_path: str, logger: Optional[logging.Logger] = None) -> func.HttpResponse:
    """Format file content based on file extension with proper HTTP headers."""
    
    # Use provided logger or create a default one
    if logger is None:
        logger = logging.getLogger('portfolio.api.helpers')
    
    # Handle JSON files with validation
    if file_path.endswith('.json'):
        try:
            json_content = json.loads(file_content)
            logger.debug(f"Successfully parsed JSON file: {file_path}")
            return func.HttpResponse(
                json.dumps(json_content, indent=2),
                status_code=200,
                mimetype="application/json",
                headers={
                    "Cache-Control": "public, max-age=900",  # 15 minutes cache
                    "Content-Type": "application/json; charset=utf-8"
                }
            )
        except json.JSONDecodeError as json_error:
            logger.warning(f"Invalid JSON in {file_path}: {str(json_error)}")
            return func.HttpResponse(
                json.dumps({
                    "error": "Invalid JSON file format",
                    "details": str(json_error)
                }),
                status_code=400,
                mimetype="application/json"
            )
    
    # Determine content type based on file extension
    content_type = "text/plain"
    if file_path.endswith('.md'):
        content_type = "text/markdown"
    elif file_path.endswith('.html'):
        content_type = "text/html"
    elif file_path.endswith('.xml'):
        content_type = "application/xml"
    elif file_path.endswith('.yaml') or file_path.endswith('.yml'):
        content_type = "application/x-yaml"
    elif file_path.endswith('.py'):
        content_type = "text/x-python"
    elif file_path.endswith('.js'):
        content_type = "text/javascript"
    elif file_path.endswith('.css'):
        content_type = "text/css"
    elif file_path.endswith('.txt'):
        content_type = "text/plain"
    
    logger.debug(f"Returning file {file_path} as {content_type}")
    
    return func.HttpResponse(
        file_content,
        status_code=200,
        mimetype=content_type,
        headers={
            "Cache-Control": "public, max-age=900",  # 15 minutes cache
            "Content-Type": f"{content_type}; charset=utf-8"
        }
    )


def handle_github_error(error: Exception, logger: Optional[logging.Logger] = None) -> func.HttpResponse:
    """Centralized GitHub error handling with specific status codes."""
    
    if logger is None:
        logger = logging.getLogger('portfolio.api.helpers')
    
    error_str = str(error).lower()
    
    # Map common GitHub API errors to appropriate HTTP status codes
    if any(phrase in error_str for phrase in ['bad credentials', 'authentication failed', 'unauthorized']):
        error_message = "GitHub authentication failed - invalid or expired token"
        status_code = 401
        logger.error(f"GitHub authentication error: {str(error)}")
        
    elif 'rate limit' in error_str:
        error_message = "GitHub API rate limit exceeded"
        status_code = 429
        logger.warning(f"GitHub rate limit exceeded: {str(error)}")
        
    elif any(phrase in error_str for phrase in ['not found', '404']):
        error_message = "Repository or file not found"
        status_code = 404
        logger.info(f"GitHub resource not found: {str(error)}")
        
    elif any(phrase in error_str for phrase in ['forbidden', '403']):
        error_message = "Access to GitHub resource forbidden"
        status_code = 403
        logger.warning(f"GitHub access forbidden: {str(error)}")
        
    elif any(phrase in error_str for phrase in ['timeout', 'timed out']):
        error_message = "Request timeout - please try again"
        status_code = 504
        logger.warning(f"GitHub request timeout: {str(error)}")
        
    elif any(phrase in error_str for phrase in ['failed to resolve', 'dns resolution', 'connection']):
        error_message = "Network connectivity issue"
        status_code = 503
        logger.error(f"GitHub network error: {str(error)}")
        
    else:
        error_message = "GitHub API error"
        status_code = 502  # Bad Gateway for upstream API issues
        logger.error(f"Unexpected GitHub error: {str(error)}", exc_info=True)
    
    return func.HttpResponse(
        json.dumps({
            "error": error_message,
            "status_code": status_code,
            "details": str(error) if status_code >= 500 else None
        }),
        status_code=status_code,
        mimetype="application/json"
    )


def trim_processed_repo(repo: dict) -> dict:
    """
    Trim repository dictionary to only include relevant keys.
    Args:
        repo: Repository dictionary with all data
    Returns:
        Dictionary with only the relevant keys preserved
    """
    keys_to_keep = [
        'id', 'name', 'url', 'description', 'fork',
        'created_at', 'updated_at', 'pushed_at', 'size',
        'language', 'license', 'allow_forking', 'topics',
        'visibility', 'file_paths',
        'total_language_bytes', 'language_percentages',
        'languages_sorted', 'relevance_scores',
        'language_relevance_score', 'matched_query_languages'
    ]
    trimmed_repo = {k: v for k, v in repo.items() if k in keys_to_keep}
    if 'owner' in repo and isinstance(repo['owner'], dict):
        trimmed_repo['owner'] = {}
        for nested_key in ['login', 'url']:
            if nested_key in repo['owner']:
                trimmed_repo['owner'][nested_key] = repo['owner'][nested_key]
    return trimmed_repo

def get_orchestration_status(instance_id: str = None, status_query_url: str = None) -> dict:
    """
    Fetch orchestration status and output from Azure Durable Functions runtime API.
    Prefer using the returned statusQueryGetUri for robustness.
    """
    import requests

    if status_query_url:
        status_url = status_query_url
        logger.debug(f"Fetching orchestration status using statusQueryGetUri: {status_url}")
        headers = {}
    elif instance_id:
        # Fallback: construct status URL from environment/config
        base_url = os.getenv("DURABLE_FUNCTIONS_BASE_URL", "http://localhost:7071")
        host_key = os.getenv("DURABLE_FUNCTIONS_HOST_KEY", "")
        task_hub = os.getenv("DURABLE_FUNCTIONS_TASK_HUB", "DurableFunctionsHub")
        connection = os.getenv("DURABLE_FUNCTIONS_CONNECTION", "Storage")
        status_url = (
            f"{base_url}/runtime/webhooks/durabletask/instances/{instance_id}"
            f"?taskHub={task_hub}&connection={connection}"
        )
        logger.debug(f"Fetching orchestration status for instance {instance_id} from {base_url}")
        logger.debug(f"Using task hub: {task_hub}, connection: {connection}, host key: {'***' if host_key else 'None'}")
        headers = {}
        if host_key:
            headers["x-functions-key"] = host_key
    else:
        logger.error("Either status_query_url or instance_id must be provided.")
        return {}

    try:
        resp = requests.get(status_url, headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        else:
            logger.error(f"Failed to fetch orchestration status: {resp.status_code} {resp.text}")
            return {}
    except Exception as e:
        logger.error(f"Error fetching orchestration status: {str(e)}")
        return {}