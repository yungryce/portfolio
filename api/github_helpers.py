from typing import Dict, List
import logging


logger = logging.getLogger('portfolio.api')


def trim_processed_repo(repo: Dict) -> Dict:
    """
    Trim repository dictionary to only include relevant keys.
    
    Args:
        repo: Repository dictionary with all data
        
    Returns:
        Dictionary with only the relevant keys preserved
    """
    # Define top-level keys to keep
    keys_to_keep = [
        'id', 'name', 'url', 'description', 'fork', 
        'created_at', 'updated_at', 'pushed_at', 'size',
        'language', 'license', 'allow_forking', 'topics', 
        'visibility', 'languages', 'repoContext',
        'total_language_bytes', 'language_percentages', 
        'languages_sorted', 'relevance_scores',
        'language_relevance_score', 'matched_query_languages'
    ]
    
    # Create new dictionary with only desired keys
    trimmed_repo = {k: v for k, v in repo.items() if k in keys_to_keep}
    
    # Handle nested owner dictionary separately
    if 'owner' in repo and isinstance(repo['owner'], dict):
        trimmed_repo['owner'] = {}
        # Only keep 'login' and 'url' from owner dictionary
        for nested_key in ['login', 'url']:
            if nested_key in repo['owner']:
                trimmed_repo['owner'][nested_key] = repo['owner'][nested_key]
    
    return trimmed_repo