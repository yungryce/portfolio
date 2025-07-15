from typing import Any, Dict, List, Optional, Union, TypeVar, Type

T = TypeVar('T')

def extract_repo_data(repo: Dict, path: str, default: Any = None, as_type: Type[T] = None) -> Union[Any, T]:
    """
    Extract data from repository using dot notation path with type conversion.
    
    Args:
        repo: Repository dictionary
        path: Dot-separated path to the data (e.g., "repoContext.tech_stack.primary")
        default: Default value if path doesn't exist
        as_type: Optional type to convert the result to (e.g., int, float, list)
        
    Returns:
        The extracted data or default value
    """
    if repo is None:
        return default
    
    current = repo
    parts = path.split('.')
    
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current.get(part)
        else:
            return default
    
    # Handle type conversion if requested
    if as_type is not None and current is not None:
        try:
            if as_type == bool and isinstance(current, str):
                return current.lower() in ('true', 'yes', '1')
            return as_type(current)
        except (ValueError, TypeError):
            return default
    
    return current if current is not None else default