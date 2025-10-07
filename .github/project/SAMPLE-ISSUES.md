# Sample GitHub Issues for Migration Project

**Purpose**: Copy these issues to your GitHub Project board to get started  
**Format**: Markdown compatible with GitHub Issues API  

---

## Phase 1: Cache Standardization Issues

### Issue #1: Audit Existing Cache Keys

**Title**: Audit and document all cache keys in cache_manager.py  
**Labels**: `phase-1: cache-layer`, `type: docs`, `priority: high`, `component: cache`  
**Milestone**: Week 1: Cache Standardization  
**Assignee**: TBD

**Description**:
Audit all cache key patterns currently used in `api/config/cache_manager.py` and document them in `CACHE-CONTRACT.md`.

**Acceptance Criteria**:
- [ ] List all cache key patterns (bundle, repo, model) with examples
- [ ] Document TTL values for each cache type
- [ ] Verify all keys follow `{type}_{username}[_{repo}][_{fingerprint}]` pattern
- [ ] Update `CACHE-CONTRACT.md` with findings

**Implementation Notes**:
- Search codebase for `cache_manager.generate_cache_key()` calls
- Check `cache_manager.get()` and `cache_manager.save()` usage
- Look for hardcoded cache keys (should be none)

**Testing Plan**:
```python
# Unit test
def test_all_cache_keys_documented():
    # Grep for cache_manager.generate_cache_key() calls
    # Verify each kind is in CACHE-CONTRACT.md
    pass
```

**Related Issues**: None (foundational task)

---

### Issue #2: Add Tenant Metadata to Blob Storage

**Title**: Store username in blob metadata for all cache entries  
**Labels**: `phase-1: cache-layer`, `type: feature`, `priority: high`, `component: cache`  
**Milestone**: Week 1: Cache Standardization  
**Assignee**: TBD

**Description**:
Update `cache_manager.save()` to store `username` in Azure Blob metadata for all cache operations. This enables per-user analytics and cleanup.

**Acceptance Criteria**:
- [ ] `cache_manager.save()` accepts `username` parameter
- [ ] Blob metadata includes `username`, `created_at`, `cache_version`
- [ ] Existing `get()` method reads metadata without breaking
- [ ] Backward compatible with blobs lacking metadata

**Implementation Notes**:
```python
# In config/cache_manager.py
def save(self, cache_key, data, ttl=None, fingerprint=None, username=None):
    metadata = {
        "created_at": datetime.now().isoformat(),
        "cache_version": "1.0"
    }
    if username:
        metadata["username"] = username
    if fingerprint:
        metadata["fingerprint"] = fingerprint
    if ttl:
        metadata["expires_at"] = (datetime.now() + timedelta(seconds=ttl)).isoformat()
    
    blob_client.upload_blob(data, metadata=metadata, overwrite=True)
```

**Testing Plan**:
```python
def test_cache_save_includes_username_metadata():
    cache_manager.save("test_key", {"data": "test"}, username="testuser")
    blob_metadata = get_blob_metadata("test_key")
    assert blob_metadata["username"] == "testuser"
```

**Dependencies**: Requires Issue #1 (documentation audit)

---

### Issue #3: Implement Quota Tracking Methods

**Title**: Add per-user quota tracking to cache_manager  
**Labels**: `phase-1: cache-layer`, `type: feature`, `priority: medium`, `component: cache`  
**Milestone**: Week 1: Cache Standardization  
**Assignee**: TBD

**Description**:
Add methods to track cache storage usage per user. This prepares for quota enforcement in Phase 4.

**Acceptance Criteria**:
- [ ] New method `get_user_cache_size(username)` returns total bytes
- [ ] New method `list_user_blobs(username)` returns blob list
- [ ] Performance: Methods use metadata filters, not full blob enumeration
- [ ] Documentation: Update `CACHE-CONTRACT.md` with usage examples

**Implementation Notes**:
```python
# In config/cache_manager.py
def get_user_cache_size(self, username: str) -> int:
    """Returns total cache size in bytes for a user."""
    total_size = 0
    container_client = self.get_container_client(self.container_name)
    
    # Filter blobs by username metadata
    for blob in container_client.list_blobs(include=['metadata']):
        if blob.metadata.get("username") == username:
            total_size += blob.size
    
    return total_size

def list_user_blobs(self, username: str) -> List[Dict]:
    """Returns list of cache entries for a user."""
    blobs = []
    container_client = self.get_container_client(self.container_name)
    
    for blob in container_client.list_blobs(include=['metadata']):
        if blob.metadata.get("username") == username:
            blobs.append({
                "name": blob.name,
                "size": blob.size,
                "created_at": blob.metadata.get("created_at"),
                "fingerprint": blob.metadata.get("fingerprint")
            })
    
    return blobs
```

**Testing Plan**:
```python
def test_get_user_cache_size():
    # Create 3 blobs for user1 (1KB each)
    cache_manager.save("key1", {"data": "x" * 1024}, username="user1")
    cache_manager.save("key2", {"data": "x" * 1024}, username="user1")
    cache_manager.save("key3", {"data": "x" * 1024}, username="user1")
    
    # Create 1 blob for user2
    cache_manager.save("key4", {"data": "x" * 1024}, username="user2")
    
    # Verify user1 size is ~3KB, user2 is ~1KB
    assert cache_manager.get_user_cache_size("user1") >= 3000
    assert cache_manager.get_user_cache_size("user2") >= 1000
```

**Dependencies**: Requires Issue #2 (metadata tagging)

---

### Issue #4: Create Application Insights Dashboard

**Title**: Build cache metrics dashboard in Application Insights  
**Labels**: `phase-1: cache-layer`, `type: infra`, `priority: high`, `component: monitoring`  
**Milestone**: Week 1: Cache Standardization  
**Assignee**: TBD

**Description**:
Create Azure Workbook (or dashboard) showing cache hit rates, sizes, and staleness per user.

**Acceptance Criteria**:
- [ ] Dashboard shows cache hit rate by user (last 24h)
- [ ] Dashboard shows cache size by user (current)
- [ ] Dashboard shows stale cache detections (fingerprint mismatches)
- [ ] KQL queries documented in `CACHE-CONTRACT.md`

**Implementation Notes**:
1. Create Azure Workbook in Azure Portal
2. Add charts using KQL queries:

**Cache Hit Rate**:
```kusto
requests
| where timestamp > ago(24h)
| where name startsWith "GET /api/bundles"
| extend username = tostring(customDimensions.username)
| extend cache_status = tostring(customDimensions.cache_status)
| summarize 
    total = count(), 
    hits = countif(cache_status == "valid")
    by username
| extend hit_rate = round(hits * 100.0 / total, 2)
| order by total desc
```

**Cache Size per User** (requires Azure CLI script):
```bash
#!/bin/bash
for user in yungryce testuser; do
    size=$(az storage blob list \
        --account-name $STORAGE_ACCOUNT \
        --container-name github-cache \
        --query "[?metadata.username=='$user'].properties.contentLength" \
        --output tsv | awk '{s+=$1} END {print s/1024/1024}')
    echo "$user: ${size} MB"
done
```

**Testing Plan**:
- Manually trigger 10 orchestrations
- Verify dashboard updates within 5 minutes
- Confirm per-user breakdown is accurate

**Dependencies**: Requires Issue #2 (metadata for filtering)

---

### Issue #5: Document Cache Service README

**Title**: Create comprehensive README for cache service  
**Labels**: `phase-1: cache-layer`, `type: docs`, `priority: medium`, `component: cache`  
**Milestone**: Week 1: Cache Standardization  
**Assignee**: TBD

**Description**:
Write `api/config/README-CACHE.md` explaining cache architecture, usage patterns, and troubleshooting.

**Acceptance Criteria**:
- [ ] Explains Azure Blob Storage architecture
- [ ] Documents all public methods in `cache_manager.py`
- [ ] Includes code examples for common operations
- [ ] Links to `CACHE-CONTRACT.md` for API spec
- [ ] Troubleshooting section (cache misses, blob errors)

**Outline**:
```markdown
# Cache Manager Service

## Architecture
- Azure Blob Storage backend
- Managed Identity authentication
- Container: `github-cache`

## Usage
### Saving Data
[code example]

### Retrieving Data
[code example]

### Checking Quota
[code example]

## Troubleshooting
### Issue: Cache always returns "missing"
Solution: Check AzureWebJobsStorage env var

## References
- [CACHE-CONTRACT.md](/.github/project/CACHE-CONTRACT.md)
```

**Testing Plan**: N/A (documentation only)

**Dependencies**: Requires Issues #1-3 (implementation details)

---

## Phase 2: Model Training Decoupling Issues

### Issue #6: Create Azure Storage Queue for Training

**Title**: Add model-training-queue to Azure Blob Storage  
**Labels**: `phase-2: model-training`, `type: infra`, `priority: high`, `component: infra`  
**Milestone**: Week 2: Model Training Queue  
**Assignee**: TBD

**Description**:
Create Azure Storage Queue named `model-training-queue` to decouple training from orchestration.

**Acceptance Criteria**:
- [ ] Queue created in same storage account as cache
- [ ] Queue accepts JSON messages with schema: `{username, fingerprint, repos_bundle}`
- [ ] Message visibility timeout: 30 minutes (training duration)
- [ ] Message TTL: 24 hours (don't retry stale training)

**Implementation Notes**:
```python
# In config/cache_manager.py or new queue_manager.py
from azure.storage.queue import QueueServiceClient

def queue_training_job(username: str, fingerprint: str, repos_bundle: List[Dict]):
    queue_client = QueueServiceClient.from_connection_string(
        os.getenv("AzureWebJobsStorage")
    ).get_queue_client("model-training-queue")
    
    message = {
        "username": username,
        "fingerprint": fingerprint,
        "repos_bundle_size": len(repos_bundle),
        "timestamp": datetime.now().isoformat()
    }
    
    # Store repos_bundle in blob, reference in message (avoid queue size limit)
    blob_key = f"training_input_{fingerprint}"
    cache_manager.save(blob_key, {"repos_bundle": repos_bundle}, ttl=86400)
    message["repos_bundle_blob"] = blob_key
    
    queue_client.send_message(json.dumps(message))
    logger.info(f"Queued training job for {username}", extra={"username": username, "fingerprint": fingerprint})
```

**Testing Plan**:
```bash
# Send test message
az storage message put \
    --queue-name model-training-queue \
    --account-name $STORAGE_ACCOUNT \
    --content '{"username":"testuser","fingerprint":"abc123"}'

# Verify message received
az storage message peek \
    --queue-name model-training-queue \
    --account-name $STORAGE_ACCOUNT
```

**Dependencies**: None (foundational infrastructure)

---

### Issue #7: Add Feature Flag for Async Training

**Title**: Implement ENABLE_ASYNC_MODEL_TRAINING feature flag  
**Labels**: `phase-2: model-training`, `type: feature`, `priority: high`, `component: api`  
**Milestone**: Week 2: Model Training Queue  
**Assignee**: TBD

**Description**:
Add feature flag to toggle between inline model training (current) and async training via queue (new).

**Acceptance Criteria**:
- [ ] Environment variable `ENABLE_ASYNC_MODEL_TRAINING` (default: `false`)
- [ ] Orchestrator checks flag before training
- [ ] If `true`: Queue training job, return immediately
- [ ] If `false`: Run inline training (existing behavior)
- [ ] Logs indicate which path was taken

**Implementation Notes**:
```python
# In function_app.py - train_semantic_model_activity
def train_semantic_model_activity(activityContext):
    username = activityContext.get('username')
    repos_bundle = activityContext.get('repos_bundle', [])
    
    enable_async = os.getenv("ENABLE_ASYNC_MODEL_TRAINING", "false").lower() == "true"
    
    if enable_async:
        logger.info(
            "Queueing async model training",
            extra={"username": username, "mode": "async"}
        )
        fingerprint = FingerprintManager.generate_content_fingerprint(repos_bundle)
        queue_training_job(username, fingerprint, repos_bundle)
        return True  # Job queued successfully
    else:
        logger.info(
            "Running inline model training",
            extra={"username": username, "mode": "inline"}
        )
        # Existing inline training logic
        semantic_model = SemanticModel()
        return semantic_model.ensure_model_ready(repos_bundle, train_if_missing=True)
```

**Testing Plan**:
1. Set `ENABLE_ASYNC_MODEL_TRAINING=false`, trigger orchestration, verify inline training
2. Set `ENABLE_ASYNC_MODEL_TRAINING=true`, trigger orchestration, verify queue message sent
3. Check logs for correct "mode" value

**Dependencies**: Requires Issue #6 (queue creation)

---

## Phase 3: GitHub Sync Optimization Issues

### Issue #8: Profile GitHub API Call Patterns

**Title**: Measure GitHub API latency and call count per orchestration  
**Labels**: `phase-3: github-sync`, `type: refactor`, `priority: medium`, `component: github`  
**Milestone**: Week 4: GitHub Sync Optimization  
**Assignee**: TBD

**Description**:
Add timing instrumentation to `github_api.py` to measure API call performance before optimization.

**Acceptance Criteria**:
- [ ] Log timing for each GitHub API call
- [ ] Count total API calls per orchestration
- [ ] Generate report: average latency per endpoint type
- [ ] Identify slowest endpoints (candidates for batching)

**Implementation Notes**:
```python
# In config/github_api.py
import time
from functools import wraps

def log_api_call(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        endpoint = kwargs.get('endpoint', 'unknown')
        
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start
            
            logger.info(
                "GitHub API call",
                extra={
                    "endpoint": endpoint,
                    "duration_ms": int(duration * 1000),
                    "status": "success"
                }
            )
            
            return result
        except Exception as e:
            duration = time.time() - start
            logger.error(
                "GitHub API call failed",
                extra={
                    "endpoint": endpoint,
                    "duration_ms": int(duration * 1000),
                    "error": str(e)
                }
            )
            raise
    
    return wrapper

class GitHubAPI:
    @log_api_call
    def get(self, endpoint, **kwargs):
        # ... existing logic
```

**Testing Plan**:
- Run full orchestration for user with 10+ repos
- Query Application Insights for API call counts and latency
- Generate report:
```kusto
traces
| where timestamp > ago(1h)
| where message == "GitHub API call"
| extend endpoint = tostring(customDimensions.endpoint)
| extend duration_ms = toint(customDimensions.duration_ms)
| summarize 
    count = count(),
    avg_ms = avg(duration_ms),
    p95_ms = percentile(duration_ms, 95)
    by endpoint
| order by count desc
```

**Dependencies**: None (measurement only)

---

## Phase 4: Multi-Tenant Preparation Issues

### Issue #9: Remove Hardcoded Username References

**Title**: Audit and remove hardcoded 'yungryce' from codebase  
**Labels**: `phase-4: multi-tenant`, `type: refactor`, `priority: high`, `component: api`  
**Milestone**: Week 5: Multi-Tenant Preparation  
**Assignee**: TBD

**Description**:
Find all hardcoded `yungryce` references in API code and replace with parameterized username.

**Acceptance Criteria**:
- [ ] Zero hardcoded `yungryce` in `api/**/*.py` (except examples/comments)
- [ ] All functions accept `username` parameter with fallback to env var
- [ ] HTTP endpoints extract `username` from request
- [ ] Tests updated to pass `username` explicitly

**Implementation Notes**:
```bash
# Find hardcoded references
cd api/
grep -r "yungryce" --include="*.py" | grep -v "# Example" | grep -v "# Default"

# Update pattern
# Before:
username = "yungryce"

# After:
username = kwargs.get('username') or os.getenv("DEFAULT_USERNAME", "yungryce")
```

**Testing Plan**:
```python
def test_no_hardcoded_usernames():
    # Grep codebase
    result = subprocess.run(
        ["grep", "-r", "yungryce", "api/", "--include=*.py"],
        capture_output=True
    )
    # Filter out comments and examples
    violations = [line for line in result.stdout.decode().split("\n") 
                  if "yungryce" in line and "#" not in line]
    assert len(violations) == 0, f"Found hardcoded usernames: {violations}"
```

**Dependencies**: None (foundational refactor)

---

### Issue #10: Add Tenant Context to All Logs

**Title**: Include username in structured logging for all API operations  
**Labels**: `phase-4: multi-tenant`, `type: refactor`, `priority: high`, `component: api`  
**Milestone**: Week 5: Multi-Tenant Preparation  
**Assignee**: TBD

**Description**:
Update all `logger.info()` and `logger.error()` calls to include `username` in `extra` dict.

**Acceptance Criteria**:
- [ ] All log statements in `api/` include `extra={"username": username}`
- [ ] Application Insights queries can filter by `customDimensions.username`
- [ ] KQL query returns per-user operation counts

**Implementation Notes**:
```python
# Update logging pattern
# Before:
logger.info(f"Processing {len(repos)} repos for {username}")

# After:
logger.info(
    "Processing repos",
    extra={
        "username": username,
        "repo_count": len(repos)
    }
)
```

**Testing Plan**:
- Run orchestration for 2 users
- Query Application Insights:
```kusto
traces
| where timestamp > ago(1h)
| extend username = tostring(customDimensions.username)
| where isnotempty(username)
| summarize count() by username, operation_Name
```
- Verify both users appear in results

**Dependencies**: Requires Issue #9 (username parameterization)

---

## Usage Instructions

### Importing to GitHub Issues

**Option 1: GitHub CLI** (recommended)
```bash
# Install gh CLI: https://cli.github.com/

# Create issues from this file
gh issue create --title "Audit existing cache keys" \
  --body-file <(sed -n '/### Issue #1/,/^---$/p' SAMPLE-ISSUES.md) \
  --label "phase-1: cache-layer,type: docs,priority: high" \
  --milestone "Week 1: Cache Standardization"

# Repeat for other issues...
```

**Option 2: Manual Copy-Paste**
1. Go to https://github.com/yungryce/portfolio/issues/new
2. Copy issue title to "Title" field
3. Copy issue body (Description through Dependencies) to "Comment" field
4. Add labels from issue header
5. Set milestone
6. Click "Submit new issue"

**Option 3: GitHub Projects Import** (future)
- Export this file as CSV
- Use GitHub Projects bulk import feature (when available)

### Issue Numbering
- Numbers (#1-#10) are samples; GitHub will auto-assign real issue numbers
- Update cross-references after creation (e.g., "Requires Issue #2" → "Requires #42")

---

**Total Issues in This File**: 10  
**Phases Covered**: 1-4 (Phases 5-6 issues TBD after Phase 4 completion)  
**Estimated Total Issues**: ~40-50 across all phases
