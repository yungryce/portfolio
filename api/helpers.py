import json
import logging
import azure.functions as func
import tiktoken
from typing import Optional, Dict, List, Any
from datetime import datetime


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


# New AI Assistant utility functions
def count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    """Count tokens in text using tiktoken."""
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except Exception:
        # Fallback to rough estimation
        return len(text) // 4


def safe_get_nested_value(data: Dict, path: str, default: Any = None) -> Any:
    """Safely get nested dictionary value using dot notation."""
    keys = path.split('.')
    current = data
    
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    
    return current


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to maximum length with suffix."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def normalize_string(value: Any) -> str:
    """Safely normalize any value to a lowercase string."""
    if value is None:
        return ""
    return str(value).lower()


def extract_keywords_from_text(text: str, min_length: int = 3) -> List[str]:
    """Extract keywords from text, filtering by minimum length."""
    if not text:
        return []
    
    words = text.lower().split()
    return [word for word in words if len(word) >= min_length]


def calculate_text_similarity(text1: str, text2: str) -> float:
    """Calculate basic text similarity using word overlap."""
    if not text1 or not text2:
        return 0.0
    
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    if not union:
        return 0.0
    
    return len(intersection) / len(union)


def validate_component_data(comp_data: Any) -> bool:
    """Validate component data structure."""
    if isinstance(comp_data, dict):
        return True
    elif isinstance(comp_data, list):
        return all(isinstance(item, dict) for item in comp_data)
    return False


def extract_component_info(comp_data: Any) -> List[Dict[str, str]]:
    """Extract component information from various data structures."""
    if isinstance(comp_data, dict):
        return [comp_data]
    elif isinstance(comp_data, list):
        return [item for item in comp_data if isinstance(item, dict)]
    return []