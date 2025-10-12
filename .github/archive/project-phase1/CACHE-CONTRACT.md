# Cache Service Contract

**Version**: 1.0  
**Status**: Draft  
**Purpose**: Define cache schema, TTL policies, and tenant isolation patterns for all CloudFolio services

---

## Overview

The cache layer is the **single source of truth** for all CloudFolio services. This document serves as the contract between:
- **Producers**: Services that write cache data (orchestrator, training service)
- **Consumers**: Services that read cache data (API endpoints, scoring service)

All services must use `cache_manager.py` as the only interface to Azure Blob Storage.

---

## Cache Storage Backend

**Technology**: Azure Blob Storage  
**Container Name**: `github-cache`  
**Access Method**: Managed Identity (User Assigned) + RBAC  
**Region**: Same as Function App (westeurope by default)  
**Redundancy**: LRS (Locally Redundant Storage)

### Blob Naming Convention
```
{cache_type}_{username}[_{repo}][_{fingerprint}]
```

Examples:
- `repos_bundle_context_yungryce`
- `repo_context_yungryce_cloudfolio`
- `model_a3f2d1e8b4c6` (fingerprint-based)

---

## Cache Key Types

### 1. Repository Bundle (`kind='bundle'`)

**Purpose**: Store aggregated data for all repositories of a user  
**Key Pattern**: `repos_bundle_context_{username}`  
**Content Type**: `application/json`  
**TTL**: 10 minutes (600 seconds)

**Data Schema**:
```json
[
  {
    "name": "repo-name",
    "fingerprint": "a3f2d1e8b4c6",
    "metadata": { /* GitHub repo metadata */ },
    "repoContext": { /* .repo-context.json content */ },
    "languages": { "Python": 5000, "JavaScript": 3000 },
    "file_types": { ".py": 10, ".js": 5 },
    "categorized_types": { "code": [".py"], "config": [".json"] },
    "readme": "# Project Title\n...",
    "skills_index": "## Skills\n...",
    "architecture": "## Architecture\n...",
    "has_documentation": true,
    "last_updated": "2025-10-07T10:30:00Z"
  }
]
```

**Blob Metadata**:
- `username`: User identifier (e.g., `yungryce`)
- `fingerprint`: Bundle-level fingerprint (generated from all repo fingerprints)
- `created_at`: ISO 8601 timestamp
- `cache_version`: Schema version (currently `1.0`)

**Invalidation Strategy**:
- Fingerprint mismatch (repo metadata changed)
- Explicit force refresh request
- TTL expiration

---

### 2. Per-Repository Cache (`kind='repo'`)

**Purpose**: Store detailed context for a single repository  
**Key Pattern**: `repo_context_{username}_{repo}`  
**Content Type**: `application/json`  
**TTL**: 30 minutes (1800 seconds)

**Data Schema**: Same as single item in Repository Bundle (see above)

**Blob Metadata**:
- `username`: User identifier
- `repo`: Repository name
- `fingerprint`: Repo-specific fingerprint (from metadata)
- `created_at`: ISO 8601 timestamp

**Invalidation Strategy**:
- Metadata fingerprint mismatch
- Bundle refresh includes this repo
- TTL expiration

---

### 3. Semantic Model Cache (`kind='model'`)

**Purpose**: Store fine-tuned model metadata and location  
**Key Pattern**: `fine_tuned_model_metadata` (global) or `model_{fingerprint}` (specific)  
**Content Type**: `application/json`  
**TTL**: None (valid until repository content changes)

**Data Schema**:
```json
{
  "storage_type": "blob",
  "container": "github-cache",
  "blob_name": "model_a3f2d1e8b4c6.zip",
  "fingerprint": "a3f2d1e8b4c6",
  "training_timestamp": "2025-10-07T12:00:00Z",
  "training_repos_count": 15,
  "repo_names": ["repo1", "repo2", "..."],
  "model_size_bytes": 200000000,
  "training_params": {
    "batch_size": 8,
    "max_pairs": 150,
    "epochs": 2,
    "use_mnrl": true
  }
}
```

**Blob Metadata**:
- `fingerprint`: Content fingerprint (from training repos)
- `created_at`: Training completion timestamp
- `cache_version`: Schema version

**Invalidation Strategy**:
- Repository content fingerprint changes (new training needed)
- Manual invalidation via admin API

---

## Cache Operations API

All operations are performed via `cache_manager.py`:

### `cache_manager.get(cache_key)`

**Returns**:
```python
{
  "status": "valid" | "missing" | "disabled" | "error" | "expired",
  "data": <parsed JSON> | None,
  "fingerprint": "a3f2d1e8b4c6" | None,
  "last_modified": datetime | None,
  "size_bytes": 1024 | None
}
```

**Status Meanings**:
- `valid`: Cache hit, data is fresh
- `expired`: Cache hit but TTL exceeded (data still returned for fallback)
- `missing`: Cache miss, no blob found
- `disabled`: Azure Storage not configured (local dev)
- `error`: Blob operation failed (network, permissions)

### `cache_manager.save(cache_key, data, ttl=None, fingerprint=None)`

**Parameters**:
- `cache_key` (str): Full blob name
- `data` (dict): JSON-serializable data
- `ttl` (int): Seconds until expiration (None = no expiry)
- `fingerprint` (str): Content fingerprint to store in metadata

**Returns**: `bool` (True if saved successfully)

**Side Effects**:
- Creates blob with metadata
- Sets `Content-Type: application/json`
- Stores `fingerprint`, `created_at`, `ttl` in blob metadata

### `cache_manager.generate_cache_key(kind, username=None, repo=None, fingerprint=None)`

**Parameters**:
- `kind` (str): `'bundle'`, `'repo'`, or `'model'`
- `username` (str): Tenant identifier (required for bundle/repo)
- `repo` (str): Repository name (required for repo)
- `fingerprint` (str): Model fingerprint (required for model)

**Returns**: `str` (formatted cache key)

**Examples**:
```python
cache_manager.generate_cache_key(kind='bundle', username='yungryce')
# → 'repos_bundle_context_yungryce'

cache_manager.generate_cache_key(kind='repo', username='yungryce', repo='cloudfolio')
# → 'repo_context_yungryce_cloudfolio'

cache_manager.generate_cache_key(kind='model', fingerprint='a3f2d1e8b4c6')
# → 'model_a3f2d1e8b4c6'
```

---

## Fingerprint Logic

Fingerprints detect changes without full content comparison.

### Metadata Fingerprint (Per-Repo)
**Input**: Repository metadata (name, updated_at, pushed_at, languages)  
**Algorithm**: SHA-256 of sorted JSON string  
**Function**: `FingerprintManager.generate_metadata_fingerprint(repo_metadata)`

**Example**:
```python
fingerprint_data = {
    "name": "cloudfolio",
    "updated_at": "2025-10-07T10:00:00Z",
    "pushed_at": "2025-10-06T15:30:00Z",
    "languages": {"Python": 5000}
}
fingerprint = hashlib.sha256(json.dumps(fingerprint_data, sort_keys=True).encode()).hexdigest()
# → 'a3f2d1e8b4c6...'
```

### Content Fingerprint (For Model Training)
**Input**: List of repository bundles with documentation  
**Algorithm**: SHA-256 of sorted README/SKILLS-INDEX/ARCHITECTURE hashes  
**Function**: `FingerprintManager.generate_content_fingerprint(repos_bundle)`

**Example**:
```python
fingerprint_data = [
    {
        "name": "repo1",
        "readme_hash": "abc123",
        "skills_hash": "def456",
        "arch_hash": "ghi789"
    }
]
fingerprint = hashlib.sha256(json.dumps(fingerprint_data, sort_keys=True).encode()).hexdigest()[:32]
# → 'a3f2d1e8...' (truncated to 32 chars)
```

---

## Multi-Tenant Isolation

### Tenant Context
All cache operations must include `username` for bundle/repo caches.

**Enforcement**:
- Cache keys include `{username}` prefix
- Blob metadata stores `username` field
- Logs include tenant context: `logger.info("Cache miss", extra={"username": username})`

### Quota Tracking (Planned)

**Per-User Limits** (soft limits initially):
- Total cache storage: 100 MB per user
- Orchestration runs per day: 50
- Model training per week: 2

**Implementation** (Phase 4):
```python
def check_user_quota(username):
    total_size = sum_blob_sizes_for_user(username)
    if total_size > 100 * 1024 * 1024:
        logger.warning(f"User {username} exceeds storage quota", extra={"username": username, "size_mb": total_size / 1024 / 1024})
        # Don't block, just warn for now
```

---

## TTL Policies

| Cache Type | TTL (seconds) | TTL (human) | Rationale |
|-----------|---------------|-------------|-----------|
| Bundle | 600 | 10 minutes | Frequent updates expected |
| Per-Repo | 1800 | 30 minutes | Individual repos change less often |
| Model | None | No expiry | Valid until training needed |

**Grace Period**: Expired cache returns data with `status: expired` but still usable as fallback.

**Manual Invalidation**: Admin API can delete specific cache entries:
```bash
curl -X DELETE https://<function-app>/api/cache/clear?username=yungryce&repo=cloudfolio
```

---

## Error Handling

### Cache Miss
```python
result = cache_manager.get(cache_key)
if result['status'] != 'valid':
    logger.info(f"Cache miss for {cache_key}, fetching fresh data")
    data = fetch_from_github(...)
    cache_manager.save(cache_key, data, ttl=600)
```

### Cache Write Failure
```python
success = cache_manager.save(cache_key, data, ttl=600)
if not success:
    logger.error(f"Failed to cache {cache_key}, continuing without cache")
    # Don't fail the request, just skip caching
```

### Blob Lease Conflicts (Concurrent Writes)
```python
# Future: Use blob leases for write safety
blob_client.acquire_lease(lease_duration=15)
try:
    blob_client.upload_blob(data, overwrite=True)
finally:
    blob_client.release_lease()
```

---

## Monitoring Queries

### Cache Hit Rate (KQL)
```kusto
requests
| where timestamp > ago(1h)
| where name startsWith "GET /api/bundles"
| extend username = tostring(customDimensions.username)
| extend cache_status = tostring(customDimensions.cache_status)
| summarize 
    total = count(), 
    hits = countif(cache_status == "valid"), 
    misses = countif(cache_status in ("missing", "expired"))
    by username
| extend hit_rate = round(hits * 100.0 / total, 2)
| order by total desc
```

### Cache Size per User (Azure CLI)
```bash
az storage blob list \
  --account-name portfoliostgXXXX \
  --container-name github-cache \
  --query "[?metadata.username=='yungryce'].properties.contentLength" \
  --output tsv | awk '{s+=$1} END {print s/1024/1024 " MB"}'
```

### Stale Cache Detection
```kusto
traces
| where timestamp > ago(1d)
| where message contains "Cache miss" or message contains "Fingerprint mismatch"
| extend username = tostring(customDimensions.username)
| extend repo = tostring(customDimensions.repo)
| summarize stale_count = count() by username, bin(timestamp, 1h)
| where stale_count > 10
| order by timestamp desc
```

---

## Local Development

### Mock Cache (No Azure Storage)
```python
# In local.settings.json, omit AzureWebJobsStorage
{
  "IsEncrypted": false,
  "Values": {
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "GITHUB_TOKEN": "ghp_xxx",
    "GROQ_API_KEY": "gsk_xxx"
    // No AzureWebJobsStorage → cache disabled
  }
}
```

Cache operations return `{"status": "disabled"}` and services fall back to fresh data.

### In-Memory Cache (Testing)
```python
# For unit tests
from unittest.mock import MagicMock
cache_manager.get = MagicMock(return_value={"status": "valid", "data": test_data})
cache_manager.save = MagicMock(return_value=True)
```

---

## Migration Notes

### Existing Cache Entries (Pre-Migration)
- Current cache keys may lack `fingerprint` metadata
- Migration script needed to backfill fingerprints
- Old cache entries expire naturally via TTL

### Breaking Changes
- **Cache version 1.0**: Current schema documented here
- **Future changes**: Bump `cache_version` in metadata, support backward compatibility for 1 version

---

## References

- Implementation: `api/config/cache_manager.py`
- Fingerprint Logic: `api/config/fingerprint_manager.py`
- Orchestrator Usage: `api/function_app.py` (orchestrator section)
- Migration Plan: [MIGRATION-PLAN.md](./MIGRATION-PLAN.md)

---

**Document Owner**: Backend Team  
**Last Updated**: October 7, 2025  
**Next Review**: End of Phase 1 (Cache Standardization)
