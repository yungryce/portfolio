# Caching Refactoring Instructions for Portfolio API

## Overview
Refactor the Portfolio API caching system to eliminate per request caching and TTL-based storage and focus on fingerprint-based caching for two primary storage levels. This aligns with the copilot instructions and simplifies cache management by removing time-based expiration.

## Storage Architecture (After Refactoring)

### Current Three Levels (Before)
1. **GitHub Request Level** (REMOVE): Individual API requests cached with TTL
2. **Repository Bundling** (KEEP): Combined bundle and per-repo bundles during orchestration  
3. **Model Bundling** (KEEP): AI model references and bundles after training

### Target Two Levels (After)
1. **Repository Bundling**: Fingerprint-based caching for `repo_context_orchestrator` and `http_start`
2. **Model Bundling**: Fingerprint-based caching for `SemanticModel` training and metadata

## Key Refactoring Rules

### 1. Remove GitHub Request Level Caching
- **Target**: Remove `@cache_manager.cache_decorator` from `make_request` in `github_api.py`
- **Reason**: Repository and model level caching provide sufficient performance
- **Impact**: Simplifies request flow, reduces cache complexity

### 2. Repository Bundle Caching (Fingerprint-Based)
- **Location**: `repo_context_orchestrator`, `http_start`, activity functions
- **Cache Keys**: `repos_bundle_context_{username}`, `repo_context_{username}_{repo}`
- **Fingerprint Logic**: Use `FingerprintManager.generate_bundle_fingerprint()` for change detection
- **No TTL**: Cache entries persist until fingerprint changes indicate repository updates
- **Container**: `github-cache` (unified container for all caching)

### 3. Model Bundle Caching (Fingerprint-Based)  
- **Location**: `SemanticModel` class methods
- **Cache Keys**: `fine_tuned_model_metadata`, `model_{fingerprint}`
- **Fingerprint Logic**: Use `FingerprintManager.generate_content_fingerprint()` for model training data
- **No TTL**: Model cache valid until training data fingerprint changes
- **Container**: `github-cache` (unified with repository caching)

## Implementation Steps

### Step 1: Remove Request-Level Caching
```python
# BEFORE: github_api.py
@cache_manager.cache_decorator(cache_key_func=generate_request_cache_key, ttl=3600)
def make_request(self, method, endpoint, **kwargs):

# AFTER: github_api.py  
def make_request(self, method, endpoint, **kwargs):
```

### Step 2: Update Repository Bundle Caching
- Remove all `ttl=` parameters from repository caching operations
- Use `cache_manager.save(key, data, ttl=None)` for persistent storage
- Implement fingerprint comparison in `http_start` and `get_stale_repos_activity`
- Ensure bundle cache uses fingerprint-based invalidation

### Step 3: Update Model Bundle Caching
- Modify `SemanticModel` to use `ttl=None` for all model-related caching
- Use repository content fingerprints to determine when to retrain models
- Store model metadata with fingerprint references for validation

### Step 4: Unify Container Usage
- All caching operations use `github-cache` container
- Remove any references to separate model containers
- Maintain existing cache key patterns for backward compatibility

## Important Constraints

### Preserve Existing Function Intent
- **Do Not Modify**: Core business logic of orchestration, model training, or data processing
- **Maintain**: All existing cache key patterns and data structures
- **Keep**: Current fingerprint generation and comparison logic

### Cache Manager Compatibility
- Use existing `CacheManager` methods: `get()`, `save()`, `delete()`
- Remove all `ttl=<number>` parameters, use `ttl=None` for persistent storage
- Maintain current cache status responses: `valid`, `missing`, `disabled`, `error`

## Testing Requirements
- Verify repository bundle caching works with fingerprint changes
- Confirm model training triggers only when content fingerprints change  
- Ensure cache cleanup still functions without TTL dependencies
- Test cache statistics and health check endpoints

## Success Criteria
1. No TTL-based cache expiration anywhere in the codebase
2. Repository bundles cache until fingerprint changes detected
3. Model bundles cache until training data fingerprint changes
4. All caching uses unified `github-cache` container
5. Performance maintained or improved with simplified caching logic
6. Existing API contracts and responses unchanged
