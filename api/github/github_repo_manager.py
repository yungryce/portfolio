import logging
import json
from typing import Dict, Any, List
from .github_api import GitHubAPI
from .github_file_manager import GitHubFileManager
from .cache_client import GitHubCache


logger = logging.getLogger('portfolio.api')

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
        'visibility', 'languages', 'file_paths',
        'total_language_bytes', 'language_percentages',
        'languages_sorted', 'relevance_scores',
        'language_relevance_score', 'matched_query_languages',
        'repoContext'
    ]
    trimmed_repo = {k: v for k, v in repo.items() if k in keys_to_keep}
    if 'owner' in repo and isinstance(repo['owner'], dict):
        trimmed_repo['owner'] = {}
        for nested_key in ['login', 'url']:
            if nested_key in repo['owner']:
                trimmed_repo['owner'][nested_key] = repo['owner'][nested_key]
    return trimmed_repo

class GitHubRepoManager:
    def __init__(self, api: GitHubAPI, cache: GitHubCache, file_manager: GitHubFileManager):
        self.api = api
        self.cache = cache
        self.file_manager = file_manager

    def get_repo_metadata(self, username: str=None, repo: str=None, include_languages: bool=False) -> Dict[str, Any]:
        """Get metadata for a specific repository.

        Args:
            username (str, optional): GitHub username. Defaults to None.
            repo (str, optional): Repository name. Defaults to None.
            include_languages (bool, optional): Whether to include language statistics. Defaults to False.

        Raises:
            ValueError: If repository name is not provided.

        Returns:
            dict: Repository metadata or None if not found.
        """
        username = username or self.api.username
        if not repo:
            raise ValueError("Repository name is required")
        endpoint = f"repos/{username}/{repo}"
        cache_key = self.cache._generate_cache_key(endpoint)
        cached = self.cache._get_from_cache(cache_key)
        if cached is not None:
            return cached
        repo_data = self.api.make_request('GET', endpoint)
        if not repo_data:
            return None
        if include_languages:
            lang_endpoint = f"repos/{username}/{repo}/languages"
            lang_cache_key = self.cache._generate_cache_key(lang_endpoint)
            lang_data = self.cache._get_from_cache(lang_cache_key)
            if lang_data is None:
                lang_data = self.api.make_request('GET', lang_endpoint)
                self.cache._save_to_cache(lang_cache_key, lang_data)
            repo_data['languages'] = lang_data or {}
        self.cache._save_to_cache(cache_key, repo_data)
        return repo_data

    def get_all_repos_metadata(self, username: str=None, per_page=100, include_languages: bool=False) -> List[Dict[str, Any]]:
        """Get metadata for all repositories.

        Args:
            username (str, optional): GitHub username. Defaults to None.
            per_page (int, optional): Number of repositories per page. Defaults to 100.
            include_languages (bool, optional): Whether to include language statistics. Defaults to False.

        Returns:
            list: List of repository metadata dictionaries.
        """
        username = username or self.api.username
        endpoint = f"users/{username}/repos"
        params = {'sort': 'updated', 'per_page': per_page}
        cache_key = self.cache._generate_cache_key(endpoint, params)
        cached = self.cache._get_from_cache(cache_key)
        if cached is not None:
            return cached
        repos = self.api.make_request('GET', endpoint, params=params)
        if not repos:
            return []
        if include_languages:
            for repo in repos:
                lang_endpoint = f"repos/{username}/{repo['name']}/languages"
                lang_cache_key = self.cache._generate_cache_key(lang_endpoint)
                lang_data = self.cache._get_from_cache(lang_cache_key)
                if lang_data is None:
                    lang_data = self.api.make_request('GET', lang_endpoint)
                    self.cache._save_to_cache(lang_cache_key, lang_data)
                repo['languages'] = lang_data or {}
        self.cache._save_to_cache(cache_key, repos)
        return repos

    def get_all_repos_with_context(self, username=None, include_languages=True):
        """
        Get all repositories with enhanced context including .repo-context.json and file paths.
        This replaces the old get_all_repos_with_files method with better naming.
        """
        username = username or self.api.username
        cache_suffix = "_with_languages" if include_languages else "_basic"
        cache_key = f"repos_with_context_{username}{cache_suffix}"
        
        cached = self.cache._get_from_cache(cache_key)
        if cached:
            logger.info(f"Using cached data ({len(cached)} repositories)")
            return cached
        
        # Get all repositories with language data
        all_repos = self.get_all_repos_metadata(username, include_languages=include_languages)
        repos_with_context = []
        
        for repo in all_repos:
            try:
                repo_name = repo['name']
                
                # Get repository context from .repo-context.json
                repo_context = self.file_manager.get_file_content(username, repo_name, '.repo-context.json')
                if repo_context and isinstance(repo_context, str):
                    try:
                        repo['repoContext'] = json.loads(repo_context)
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON in .repo-context.json for {repo_name}")
                        repo['repoContext'] = {}
                else:
                    repo['repoContext'] = {}
                
                # Get root directory file listing
                if 'contents_url' in repo:
                    try:
                        root_files = self.file_manager.get_file_content(username, repo_name, "")
                        if isinstance(root_files, list):
                            # Extract file paths for efficient processing
                            file_paths = [item.get('path') for item in root_files 
                                        if isinstance(item, dict) and 'path' in item]
                            repo['file_paths'] = file_paths
                    except Exception as e:
                        logger.warning(f"Failed to get file listing for {repo_name}: {str(e)}")
                
                # Trim to only relevant fields
                trimmed_repo = trim_processed_repo(repo)
                repos_with_context.append(trimmed_repo)
                
            except Exception as e:
                logger.warning(f"Failed to enhance {repo.get('name', 'unknown')}: {str(e)}")
                # Ensure repo has required fields even on error
                if 'languages' not in repo and include_languages:
                    repo['languages'] = {}
                repo['repoContext'] = {}
                trimmed_repo = trim_processed_repo(repo)
                repos_with_context.append(trimmed_repo)
        
        # Cache the enhanced result
        self.cache._save_to_cache(cache_key, repos_with_context, ttl=3600)  # 1 hour cache
        
        logger.info(f"Enhanced {len(repos_with_context)} repositories with context for {username}")
        return repos_with_context

    # Keep the old method name for backward compatibility
    def get_all_repos_with_files(self, username=None, include_languages=True):
        """Deprecated: Use get_all_repos_with_context instead."""
        logger.warning("get_all_repos_with_files is deprecated. Use get_all_repos_with_context instead.")
        return self.get_all_repos_with_context(username, include_languages)

    def get_repository_tree(self, username: str, repo_name: str, recursive: bool = False) -> List[str]:
        """
        Recursively fetch all file paths in a repository.
        Returns a flat list of file paths (including nested files).
        """
        def _fetch_tree(path=""):
            files = []
            try:
                contents = self.file_manager.get_file_content(username, repo_name, path)
                if isinstance(contents, list):
                    for item in contents:
                        if item.get('type') == 'file':
                            files.append(item.get('path'))
                        elif item.get('type') == 'dir' and recursive:
                            # Recursively fetch files in subdirectory
                            sub_path = item.get('path')
                            files.extend(_fetch_tree(sub_path))
                # If contents is a dict (single file), add its path
                elif isinstance(contents, dict) and contents.get('type') == 'file':
                    files.append(contents.get('path'))
            except Exception as e:
                logger.warning(f"Error fetching tree for {repo_name} at '{path}': {str(e)}")
            return files

        return _fetch_tree("")