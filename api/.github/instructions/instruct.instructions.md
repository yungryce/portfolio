# Centralized Caching Instructions for Portfolio API

## Overview
This document provides a unified approach to managing caching across the Portfolio API. The goal is to centralize caching logic, ensure consistency, and simplify maintenance. The caching system will handle three levels of caching:

1. **Low-Level Request Caching**: Caches responses from external APIs (e.g., GitHub API).
2. **Bundle Caching**: Caches repository bundles (individual and aggregated) during orchestration.
3. **Metadata Caching**: Caches metadata for trained models.

## Centralized Caching System
All caching will be managed centrally using a single `CacheManager` class. This class will:
- Handle all cache operations (get, save, delete).
- Support dynamic TTL (e.g., `ttl=None` for no expiration).
- Provide a consistent interface for all caching levels.
- Ensure backward compatibility to avoid breaking changes.

### Key Features
1. **Dynamic TTL**:
   - `ttl=None`: Cache entries do not expire and are updated only when changes are detected.
   - `ttl=<seconds>`: Cache entries expire after the specified duration.

2. **Change Detection**:
   - For bundles: Use repository fingerprints to detect changes.
   - For models: Use repository fingerprints and metadata to detect changes.

3. **Centralized Logic**:
   - All caching logic will be moved to the `CacheManager` class.
   - Existing caching calls will be refactored to use this class.

4. **Backward Compatibility**:
   - Existing cache keys and structures will remain unchanged.
   - Transition will be seamless without breaking existing functionality.

## Implementation Plan

### 1. Create `CacheManager` Class
The `CacheManager` class will be responsible for all caching operations. It will:
- Use Azure Blob Storage for storing cache entries.
- Support dynamic TTL and no-expiry entries.
- Provide methods for getting, saving, and deleting cache entries.
- Include a decorator for abstracting repetitive caching logic.

#### Example Methods and Decorator
```python
class CacheManager:
    def __init__(self, container_name: str, default_ttl: int = 21600):
        self.container_name = container_name
        self.default_ttl = default_ttl
        self.blob_service_client = BlobServiceClient.from_connection_string(os.getenv('AzureWebJobsStorage'))

    def get(self, cache_key: str) -> Dict[str, Any]:
        """Retrieve a cache entry."""
        # Logic for retrieving cache entry

    def save(self, cache_key: str, data: Any, ttl: Optional[int] = None):
        """Save a cache entry with optional TTL."""
        # Logic for saving cache entry

    def delete(self, cache_key: str):
        """Delete a cache entry."""
        # Logic for deleting cache entry

    def cache_decorator(self, cache_key_func: Callable, ttl: Optional[int] = None):
        """Decorator to handle caching logic."""
        def decorator(func):
            def wrapper(*args, **kwargs):
                cache_key = cache_key_func(*args, **kwargs)
                cached_data = self.get(cache_key)
                if cached_data:
                    return cached_data
                result = func(*args, **kwargs)
                self.save(cache_key, result, ttl=ttl)
                return result
            return wrapper
        return decorator
```

### 2. Refactor Existing Caching Logic

#### Low-Level Request Caching
- Update `make_request` in `GitHubAPI` to use the `cache_decorator` for caching responses.
- Cache key: `request:<method>:<endpoint>:<params_hash>`.

#### Example Usage
```python
cache_manager = CacheManager(container_name="github-cache")

def generate_request_cache_key(method, endpoint, params):
    return f"request:{method}:{endpoint}:{hashlib.md5(str(params).encode()).hexdigest()}"

class GitHubAPI:
    @cache_manager.cache_decorator(cache_key_func=generate_request_cache_key, ttl=3600)
    def make_request(self, method: str, endpoint: str, params: Dict[str, Any]):
        # Logic for making API request
        pass
```

#### Bundle Caching
- Update `repo_context_orchestrator` to use the `cache_decorator` for caching repository bundles.
- Cache key: `bundle:<username>:<repo_name>` for individual bundles.
- Cache key: `bundle:<username>:all` for aggregated bundles.

#### Example Usage
```python
def generate_bundle_cache_key(username, repo_name=None):
    return f"bundle:{username}:{repo_name or 'all'}"

class RepoContextOrchestrator:
    @cache_manager.cache_decorator(cache_key_func=generate_bundle_cache_key, ttl=None)
    def get_bundle(self, username: str, repo_name: Optional[str] = None):
        # Logic for generating repository bundle
        pass
```

#### Metadata Caching
- Update `SemanticModel` to use the `cache_decorator` for caching model metadata.
- Cache key: `model_metadata:<fingerprint>`.

#### Example Usage
```python
def generate_metadata_cache_key(fingerprint):
    return f"model_metadata:{fingerprint}"

class SemanticModel:
    @cache_manager.cache_decorator(cache_key_func=generate_metadata_cache_key, ttl=None)
    def generate_metadata(self, fingerprint: str):
        # Logic for generating model metadata
        pass
```

### 3. Support Dynamic TTL
- Modify `CacheManager` to handle `ttl=None` for no-expiry entries.
- Ensure backward compatibility by defaulting to `default_ttl` if `ttl` is not provided.

### 4. Transition Plan
- Implement `CacheManager` without modifying existing functionality.
- Gradually refactor existing caching logic to use `CacheManager` and its decorator.
- Test each refactored component to ensure no breaking changes.

## Testing and Validation
- Unit tests for `CacheManager` methods and decorator.
- Integration tests for refactored components.
- End-to-end tests to ensure no breaking changes.

## Summary
This centralized caching approach will:
- Simplify caching logic using decorators.
- Ensure consistency across all caching levels.
- Support dynamic TTL and no-expiry entries.
- Maintain backward compatibility during the transition.
