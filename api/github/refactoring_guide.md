# Refactoring Guide: Transitioning to CacheManager

This guide provides step-by-step instructions for refactoring code to use the new `CacheManager` class with decorators instead of the existing `GitHubCache` implementation.

## Overview

The new `CacheManager` class provides a more centralized and flexible approach to caching, with the following improvements:
- Decorator-based caching for cleaner code
- Support for non-expiring cache entries
- Consistent interface for all caching levels
- Dynamic TTL handling

## Step 1: Import the New CacheManager

Replace imports of `GitHubCache` with the new `CacheManager` or use the global instance:

```python
# Before
from github.cache_client import GitHubCache

# After - Option 1: Use the global instance
from github.cache_manager import cache_manager

# After - Option 2: Import the class if you need a custom instance
from github.cache_manager import CacheManager
```

## Step 2: Define Cache Key Functions

Define functions to generate cache keys for your specific use cases:

```python
def generate_request_cache_key(method, endpoint, params=None):
    """Generate a cache key for a GitHub API request."""
    normalized_endpoint = endpoint.lstrip('/').replace('/', '_').replace('?', '_').replace('&', '_')
    if params:
        param_string = str(params)
        param_hash = hashlib.md5(param_string.encode()).hexdigest()[:8]
        return f"request:{method}:{normalized_endpoint}:{param_hash}"
    return f"request:{method}:{normalized_endpoint}"
```

## Step 3: Apply Decorators

Replace manual cache checking and saving with decorators:

```python
# Before
def make_request(self, method: str, endpoint: str, params: Dict[str, Any] = None):
    cache_key = self.cache._generate_cache_key(endpoint, params)
    cache_result = self.cache._get_from_cache(cache_key)
    if cache_result['status'] == 'valid':
        return cache_result['data']
    
    # Make actual request
    response = self._perform_request(method, endpoint, params)
    
    # Save to cache
    self.cache._save_to_cache(cache_key, response, ttl=3600)
    return response

# After
@cache_manager.cache_decorator(cache_key_func=generate_request_cache_key, ttl=3600)
def make_request(self, method: str, endpoint: str, params: Dict[str, Any] = None):
    # Make actual request
    return self._perform_request(method, endpoint, params)
```

## Step 4: Update Cache Operations

For cases where you need direct cache operations:

```python
# Before
cache = GitHubCache()
cache._save_to_cache(key, data, ttl=3600)
result = cache._get_from_cache(key)

# After
cache_manager.save(key, data, ttl=3600)
result = cache_manager.get(key)
```

## Step 5: Handle Non-Expiring Cache

For cases where you want cache entries that never expire:

```python
# Before - No direct equivalent
cache._save_to_cache(key, data, ttl=timedelta(days=365).total_seconds())

# After
cache_manager.save(key, data, ttl=None)
```

## Example Refactoring: GitHubAPI

Here's an example of refactoring the `make_request` method in `GitHubAPI`:

```python
# Before
def make_request(self, method: str, endpoint: str, params: Dict[str, Any] = None):
    if self.cache and self.use_cache:
        cache_key = self.cache._generate_cache_key(endpoint, params)
        cache_result = self.cache._get_from_cache(cache_key)
        if cache_result['status'] == 'valid':
            return cache_result['data']
    
    # Make request
    url = f"{self.api_url}/{endpoint.lstrip('/')}"
    headers = {"Authorization": f"token {self.token}"}
    response = requests.request(method, url, headers=headers, params=params)
    response.raise_for_status()
    data = response.json()
    
    if self.cache and self.use_cache:
        self.cache._save_to_cache(cache_key, data, ttl=3600)
    
    return data

# After
def generate_request_cache_key(self, method, endpoint, params=None):
    normalized_endpoint = endpoint.lstrip('/').replace('/', '_').replace('?', '_').replace('&', '_')
    if params:
        param_string = str(params)
        param_hash = hashlib.md5(param_string.encode()).hexdigest()[:8]
        return f"request:{method}:{normalized_endpoint}:{param_hash}"
    return f"request:{method}:{normalized_endpoint}"

@cache_manager.cache_decorator(cache_key_func=generate_request_cache_key, ttl=3600)
def make_request(self, method: str, endpoint: str, params: Dict[str, Any] = None):
    # Make request
    url = f"{self.api_url}/{endpoint.lstrip('/')}"
    headers = {"Authorization": f"token {self.token}"}
    response = requests.request(method, url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()
```

## Example Refactoring: Orchestrator

Here's an example of refactoring repository bundle caching:

```python
# Before
def get_repo_context_bundle(self, username: str, repo_name: str):
    cache_key = f"repo_context_{username}_{repo_name}"
    cache_result = self.cache._get_from_cache(cache_key)
    if cache_result['status'] == 'valid':
        return cache_result['data']
    
    # Generate bundle
    bundle = self._generate_repo_bundle(username, repo_name)
    
    # Save to cache
    self.cache._save_to_cache(cache_key, bundle, ttl=12*3600)  # 12 hours
    
    return bundle

# After
def generate_bundle_cache_key(self, username, repo_name):
    return f"repo_context_{username}_{repo_name}"

@cache_manager.cache_decorator(cache_key_func=generate_bundle_cache_key, ttl=12*3600)
def get_repo_context_bundle(self, username: str, repo_name: str):
    # Generate bundle
    return self._generate_repo_bundle(username, repo_name)
```

## Testing the Transition

1. Begin by refactoring non-critical components first.
2. Write unit tests to verify that the refactored code works as expected.
3. Compare cache operations before and after to ensure consistency.
4. Gradually refactor more critical components as confidence builds.

## Handling Special Cases

### Cache Cleanup

Replace calls to `GitHubCache.cleanup_expired_cache` with `CacheManager.cleanup_expired_cache`:

```python
# Before
cache = GitHubCache()
result = cache.cleanup_expired_cache(batch_size=100, dry_run=False)

# After
result = cache_manager.cleanup_expired_cache(batch_size=100, dry_run=False)
```

### Cache Statistics

Replace calls to `GitHubCache.get_cache_statistics` with `CacheManager.get_cache_statistics`:

```python
# Before
cache = GitHubCache()
stats = cache.get_cache_statistics()

# After
stats = cache_manager.get_cache_statistics()
```

## Conclusion

This refactoring simplifies caching logic, makes code more maintainable, and adds support for non-expiring cache entries. The decorator-based approach reduces boilerplate code and ensures consistent caching behavior throughout the application.
