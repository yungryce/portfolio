"""
GitHub API integration package for the Portfolio API.

This package provides integration with the GitHub API, including:
- Raw API requests
- Caching of API responses
- File and directory management
- Repository metadata management
"""

from github.github_api import GitHubAPI
from Samples.cache_client import GitHubCache
from github.cache_manager import CacheManager, cache_manager
from github.github_file_manager import GitHubFileManager
from github.github_repo_manager import GitHubRepoManager

__all__ = [
    'GitHubAPI',
    'GitHubCache',
    'GitHubFileManager',
    'GitHubRepoManager',
    'CacheManager',
    'cache_manager'
]
