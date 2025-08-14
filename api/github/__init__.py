"""
GitHub API integration package for the Portfolio API.

This package provides integration with the GitHub API, including:
- Raw API requests
- Caching of API responses
- File and directory management
- Repository metadata management
"""

from github.github_api import GitHubAPI
from github.cache_manager import CacheManager, cache_manager
from github.github_repo_manager import GitHubRepoManager
from github.fingerprint_manager import FingerprintManager

__all__ = [
    'GitHubAPI',
    'GitHubRepoManager',
    'CacheManager',
    'cache_manager',
    'FingerprintManager'
]
