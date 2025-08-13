import logging
import json
import os
import requests
import time
from typing import Dict, Any, List, Optional
from .github_api import GitHubAPI
from .cache_manager import cache_manager
from fa_helpers import trim_processed_repo


logger = logging.getLogger('portfolio.api')

class GitHubRepoManager:
    def __init__(self, api: GitHubAPI, file_manager: GitHubFileManager, username: Optional[str] = None):
        """Initialize the GitHubRepoManager with API, cache, and file manager."""
        self.api = api
        self.username = username

    @cache_manager.cache_decorator(cache_key_func=lambda username, repo: f"repos:{username}:{repo}", ttl=3600)
    def get_repo_metadata(self, username: Optional[str]=None, repo: Optional[str]=None, include_languages: bool=False) -> Dict[str, Any]:
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
        username = username or self.username
        if not repo:
            raise ValueError("Repository name is required")
        endpoint = f"repos/{username}/{repo}"
        repo_data = self.api.make_request('GET', endpoint)
        if not isinstance(repo_data, dict):
            raise ValueError("Invalid response format for repository metadata")
        if include_languages:
            languages = self.api.make_request('GET', f"{endpoint}/languages")
            if isinstance(languages, dict):
                repo_data['languages'] = languages
        return repo_data

    @cache_manager.cache_decorator(
    cache_key_func=lambda username=None, per_page=100, include_languages=False: f"repos:{username}:all", 
    ttl=3600
    )
    def get_all_repos_metadata(self, username: Optional[str]=None, per_page=100, include_languages: bool=False) -> List[Dict[str, Any]]:
        """Get metadata for all repositories.

        Args:
            username (str, optional): GitHub username. Defaults to None.
            per_page (int, optional): Number of repositories per page. Defaults to 100.
            include_languages (bool, optional): Whether to include language statistics. Defaults to False.

        Returns:
            list: List of repository metadata dictionaries.
        """
        username = username or self.username
        if not username:
            raise ValueError("Username is required")
        endpoint = f"users/{username}/repos"
        
        repos = self.api.make_request('GET', endpoint, params={'per_page': per_page})
        if not isinstance(repos, list):
            raise ValueError("Invalid response format for repositories metadata")
        if include_languages:
            for repo in repos:
                if isinstance(repo, dict) and 'name' in repo:
                    languages = self.api.make_request('GET', f"repos/{username}/{repo['name']}/languages")
                    if isinstance(languages, dict):
                        repo['languages'] = languages
        return repos
    
    @cache_manager.cache_decorator(cache_key_func=lambda username, repo, path: f"file_content:{username}:{repo}:{path}", ttl=3600)
    def get_file_content(self, username: Optional[str], repo: str, path: str) -> Optional[str]:
        """
        Fetch the content of a file from a repository using the underlying file_manager.
        Args:
            repo_name: Name of the repository
            path: Path to the file (e.g., 'README.md')
            username: GitHub username (optional, defaults to self.api.username)
        Returns:
            File content as a string, or None if not found.
        """
        if not username:
            raise ValueError("Username is required")
        endpoint = f"repos/{username}/{repo}/contents/{path}"
        file_data = self.api.make_request('GET', endpoint)
        if isinstance(file_data, dict) and file_data.get('type') == 'file':
            return self.api.decode_file_content(file_data)
        return None

    @cache_manager.cache_decorator(cache_key_func=lambda username, repo: f"repos_with_context:{username}:{repo}", ttl=None)
    def get_all_repos_with_context(self, username: Optional[str], include_languages: bool = True):
        """
        Get all repositories with enhanced context including .repo-context.json and file paths.
        This replaces the old get_all_repos_with_files method with better naming.
        """
        if not username:
            raise ValueError("Username is required")
        username = str(username)  # Ensure username is a string
        repos = self.get_all_repos_metadata(username, include_languages=include_languages)
        repos_with_context = [trim_processed_repo(repo) for repo in repos if isinstance(repo, dict)]
        return repos_with_context

    # Keep the old method name for backward compatibility
    def get_all_repos_with_files(self, username=None, include_languages=True):
        """Deprecated: Use get_all_repos_with_context instead."""
        logger.warning("get_all_repos_with_files is deprecated. Use get_all_repos_with_context instead.")
        return self.get_all_repos_with_context(username, include_languages)

    def get_repository_tree(self, repo_name: str, username: Optional[str] = None, recursive: bool = False) -> List[str]:
        """
        Recursively fetch all file paths in a repository.
        Returns a flat list of file paths (including nested files).
        """
        username = username or self.username

        def _fetch_tree(path: str = "") -> List[str]:
            files: List[str] = []
            try:
                contents = self.file_manager.list_directory(username, repo_name, path)
                for item in contents:
                    if item.get('type') == 'file':
                        files.append(item.get('path'))
                    elif item.get('type') == 'dir' and recursive:
                        sub_path = item.get('path')
                        files.extend(_fetch_tree(sub_path))
                    elif isinstance(contents, dict) and contents.get('type') == 'file':
                        files.append(contents.get('path'))
            except Exception as e:
                logger.warning(f"Error fetching tree for {repo_name} at '{path}': {str(e)}")
            return files

        return _fetch_tree("")

    @cache_manager.cache_decorator(cache_key_func=lambda repo_name, username: f"file_types:{username}:{repo_name}", ttl=3600)
    def get_all_file_types(self, repo_name: str, username: Optional[str] = None) -> Dict[str, int]:
        """
        Recursively retrieve all file types/extensions in a repository.
        """
        if not username:
            raise ValueError("Username is required")
        endpoint = f"repos/{username}/{repo_name}/languages"
        languages = self.api.make_request('GET', endpoint)
        if not isinstance(languages, dict):
            raise ValueError("Invalid response format for file types")
        return languages