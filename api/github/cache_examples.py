import hashlib
import logging
from typing import Dict, Any, Optional, List
from github.cache_manager import cache_manager

logger = logging.getLogger('portfolio.api')

# Example 1: Low-Level Request Caching with GitHub API
def generate_request_cache_key(self, method, endpoint, params=None):
    """Generate a cache key for a GitHub API request."""
    normalized_endpoint = endpoint.lstrip('/').replace('/', '_').replace('?', '_').replace('&', '_')
    if params:
        param_string = str(params)
        param_hash = hashlib.md5(param_string.encode()).hexdigest()[:8]
        return f"request:{method}:{normalized_endpoint}:{param_hash}"
    return f"request:{method}:{normalized_endpoint}"

class GitHubAPIExample:
    """Example of using the cache decorator with GitHub API requests."""
    
    @cache_manager.cache_decorator(cache_key_func=generate_request_cache_key, ttl=3600)
    def make_request(self, method: str, endpoint: str, params: Dict[str, Any] = None):
        """Make a request to the GitHub API with caching."""
        # Here you would normally make the actual API request
        # For example:
        # response = requests.request(method, f"{self.base_url}/{endpoint}", params=params)
        # return response.json()
        
        # Simulated response for example
        logger.info(f"Making API request: {method} {endpoint}")
        return {"simulated": "response", "method": method, "endpoint": endpoint}


# Example 2: Bundle Caching for Orchestrator
def generate_bundle_cache_key(username, repo_name=None):
    """Generate a cache key for repository bundles."""
    if repo_name:
        return f"bundle:{username}:{repo_name}"
    return f"bundle:{username}:all"

class RepoContextOrchestratorExample:
    """Example of using the cache decorator with repository bundle caching."""
    
    @cache_manager.cache_decorator(cache_key_func=generate_bundle_cache_key, ttl=None)  # No expiration
    def get_bundle(self, username: str, repo_name: Optional[str] = None):
        """Get a repository bundle with caching."""
        # Here you would normally generate the bundle
        # For example:
        # if repo_name:
        #     return self._fetch_single_repo_bundle(username, repo_name)
        # else:
        #     return self._fetch_all_repos_bundle(username)
        
        # Simulated bundle for example
        logger.info(f"Generating bundle for {username}/{repo_name or 'all'}")
        return {
            "username": username,
            "repo": repo_name or "all_repos",
            "data": "Simulated bundle data"
        }


# Example 3: Metadata Caching for Semantic Models
def generate_metadata_cache_key(fingerprint):
    """Generate a cache key for model metadata."""
    return f"model_metadata:{fingerprint}"

class SemanticModelExample:
    """Example of using the cache decorator with model metadata caching."""
    
    @cache_manager.cache_decorator(cache_key_func=generate_metadata_cache_key, ttl=None)  # No expiration
    def generate_metadata(self, fingerprint: str):
        """Generate model metadata with caching."""
        # Here you would normally generate the model metadata
        # For example:
        # return self._compute_model_metadata(fingerprint)
        
        # Simulated metadata for example
        logger.info(f"Generating metadata for fingerprint {fingerprint}")
        return {
            "fingerprint": fingerprint,
            "model_type": "sentence-transformer",
            "created_at": "2025-08-10T12:00:00Z",
            "stats": {
                "training_examples": 1000,
                "accuracy": 0.95
            }
        }


def usage_example():
    """Example of how to use the decorated classes."""
    # Example 1: GitHub API
    github_api = GitHubAPIExample()
    response = github_api.make_request("GET", "users/yungryce")
    print("GitHub API Response:", response)
    
    # Example 2: Repository Bundle
    orchestrator = RepoContextOrchestratorExample()
    bundle = orchestrator.get_bundle("yungryce", "portfolio")
    print("Repo Bundle:", bundle)
    
    # Example 3: Model Metadata
    model = SemanticModelExample()
    metadata = model.generate_metadata("model-2025-08-10")
    print("Model Metadata:", metadata)


if __name__ == "__main__":
    usage_example()
