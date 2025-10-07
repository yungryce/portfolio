# AI Agent Development Guide

**Purpose**: Enable AI coding agents (GitHub Copilot, Cursor, etc.) to efficiently work on CloudFolio migration tasks  
**Audience**: AI agents and human developers using AI assistants  
**Version**: 1.0

---

## Quick Start for AI Agents

### Context Loading Priority
When starting a new task, load context in this order:
1. **Task-specific docs**: Read the relevant phase docs (CACHE-CONTRACT.md, MIGRATION-PLAN.md, etc.)
2. **Current code**: Examine the files mentioned in the task issue
3. **Copilot instructions**: Review `.github/copilot-instructions.md` for project patterns
4. **Architecture**: Skim `ARCHITECTURE.md` for system overview

### File Navigation Map
```
cloudfolio/
├── .github/
│   ├── copilot-instructions.md        # Global coding patterns
│   └── project/                        # Migration-specific docs (YOU ARE HERE)
│       ├── MIGRATION-PLAN.md          # Overall strategy
│       ├── CACHE-CONTRACT.md          # Cache API reference
│       ├── MULTI-TENANT-DESIGN.md     # Tenant isolation patterns
│       └── AI-AGENT-GUIDE.md          # This file
│
├── api/                                # Backend (Python Azure Functions)
│   ├── function_app.py                # Main entry point (routes + orchestrator)
│   ├── fa_helpers.py                  # HTTP response utilities
│   ├── config/
│   │   ├── cache_manager.py           # Cache operations (CRITICAL)
│   │   ├── fingerprint_manager.py     # Change detection logic
│   │   ├── github_api.py              # GitHub REST client
│   │   ├── github_repo_manager.py     # High-level repo operations
│   │   └── fine_tuning.py             # Model training (compute-heavy)
│   └── ai/
│       ├── ai_assistant.py            # Groq LLM integration
│       ├── repo_scoring_service.py    # Semantic scoring
│       └── type_analyzer.py           # File type categorization
│
├── src/                                # Frontend (Angular 17+)
│   ├── app/
│   │   ├── projects/                  # Repository list & detail views
│   │   ├── assistant/                 # AI chat interface
│   │   └── services/                  # API clients
│   └── environments/                   # API base URLs
│
└── infra/
    ├── main.bicep                      # Infrastructure as Code
    └── modules/                        # Reusable Bicep modules (future)
```

---

## Coding Patterns & Conventions

### 1. Cache Operations
**Always** use `cache_manager.py` for storage operations:

```python
# ✅ CORRECT: Use cache_manager
from config.cache_manager import cache_manager

cache_key = cache_manager.generate_cache_key(kind='bundle', username=username)
result = cache_manager.get(cache_key)

if result['status'] == 'valid':
    data = result['data']
else:
    data = fetch_from_github(...)
    cache_manager.save(cache_key, data, ttl=600, fingerprint=fingerprint)

# ❌ WRONG: Direct Azure Blob access
from azure.storage.blob import BlobServiceClient
blob_client = BlobServiceClient(...).get_blob_client(...)  # Don't do this
```

**Reference**: [CACHE-CONTRACT.md](./CACHE-CONTRACT.md)

---

### 2. Error Handling
**Always** return standardized HTTP responses:

```python
from fa_helpers import create_success_response, create_error_response, handle_github_error

# ✅ CORRECT: Structured responses
try:
    data = process_request()
    return create_success_response({"data": data})
except GitHubException as e:
    return handle_github_error(e)  # Handles 403, 404, 429 specially
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    return create_error_response(str(e), 500)

# ❌ WRONG: Raw JSON responses
return func.HttpResponse(json.dumps({"data": data}), status_code=200)  # Don't do this
```

---

### 3. Tenant Context in Logs
**Always** include `username` in log statements:

```python
# ✅ CORRECT: Structured logging
logger.info(
    "Processing repository bundle",
    extra={
        "username": username,
        "repo_count": len(repos),
        "operation": "orchestration"
    }
)

# ❌ WRONG: Plain string logging
logger.info(f"Processing {len(repos)} repos for user {username}")  # Harder to query
```

**Why**: Application Insights can filter by `customDimensions.username` for per-user debugging.

---

### 4. Feature Flags
**Always** wrap new behavior in feature flags during migration:

```python
import os

# ✅ CORRECT: Feature flag with fallback
enable_async_training = os.getenv("ENABLE_ASYNC_MODEL_TRAINING", "false").lower() == "true"

if enable_async_training:
    queue_training_job(username, fingerprint, repos_bundle)
else:
    train_model_inline(repos_bundle)  # Existing behavior

# ❌ WRONG: Direct behavior change
queue_training_job(username, fingerprint, repos_bundle)  # Can't rollback easily
```

**Reference**: [MIGRATION-PLAN.md](./MIGRATION-PLAN.md#phase-2-model-training-decoupling-week-2-3)

---

### 5. Fingerprint Validation
**Always** check fingerprints before expensive operations:

```python
from config.fingerprint_manager import FingerprintManager

# ✅ CORRECT: Fingerprint-based staleness check
current_fingerprint = FingerprintManager.generate_metadata_fingerprint(repo_metadata)
cached_fingerprint = cached_bundle.get('fingerprint')

if current_fingerprint == cached_fingerprint:
    logger.info("Using cached bundle (fingerprint match)", extra={"username": username})
    return cached_bundle
else:
    logger.info("Refetching bundle (fingerprint mismatch)", extra={"username": username})
    return fetch_fresh_bundle(username)

# ❌ WRONG: TTL-only caching
if cache_age < 600:  # 10 minutes
    return cached_bundle  # May miss recent changes
```

---

## Common Task Workflows

### Task: Add New Cache Type
**Example**: Add per-user settings cache

**Steps**:
1. **Define schema** in `CACHE-CONTRACT.md`:
   ```markdown
   ### 4. User Settings Cache (`kind='settings'`)
   **Key Pattern**: `user_settings_{username}`
   **TTL**: 1 hour (3600 seconds)
   **Data Schema**: `{"theme": "dark", "notifications": true}`
   ```

2. **Update `cache_manager.generate_cache_key()`**:
   ```python
   def generate_cache_key(self, kind, username=None, repo=None, fingerprint=None):
       if kind == 'settings':
           if not username:
               raise ValueError("username required for settings cache")
           return f"user_settings_{username}"
       # ... existing kinds
   ```

3. **Create getter/setter functions**:
   ```python
   def get_user_settings(username: str) -> dict:
       cache_key = cache_manager.generate_cache_key(kind='settings', username=username)
       result = cache_manager.get(cache_key)
       return result.get('data', {})
   
   def save_user_settings(username: str, settings: dict):
       cache_key = cache_manager.generate_cache_key(kind='settings', username=username)
       cache_manager.save(cache_key, settings, ttl=3600)
   ```

4. **Add HTTP endpoint**:
   ```python
   @app.route(route="settings/{username}", methods=["GET", "POST"])
   def user_settings(req: func.HttpRequest) -> func.HttpResponse:
       username = req.route_params.get('username')
       
       if req.method == "GET":
           settings = get_user_settings(username)
           return create_success_response(settings)
       
       elif req.method == "POST":
           settings = req.get_json()
           save_user_settings(username, settings)
           return create_success_response({"status": "saved"})
   ```

5. **Update tests** (if test suite exists).

---

### Task: Add Monitoring Query
**Example**: Track model training failures per user

**Steps**:
1. **Identify log statements** emitting training events:
   ```python
   # In api/function_app.py - train_semantic_model_activity
   logger.info(f"Semantic model training {'succeeded' if model_ready else 'failed'}")
   ```

2. **Add structured fields** for queryability:
   ```python
   logger.info(
       "Model training completed",
       extra={
           "username": username,
           "success": model_ready,
           "training_duration_sec": training_time,
           "fingerprint": fingerprint
       }
   )
   ```

3. **Create KQL query** in Application Insights:
   ```kusto
   traces
   | where timestamp > ago(7d)
   | where message contains "Model training completed"
   | extend username = tostring(customDimensions.username)
   | extend success = tobool(customDimensions.success)
   | summarize 
       total_trainings = count(),
       failures = countif(success == false),
       avg_duration_sec = avg(todouble(customDimensions.training_duration_sec))
       by username
   | order by failures desc
   ```

4. **Add to monitoring dashboard** (Azure Workbook or custom HTML).

5. **Set up alert rule** (optional):
   ```kusto
   // Alert if failure rate > 20%
   traces
   | where timestamp > ago(1h)
   | where message contains "Model training completed"
   | extend success = tobool(customDimensions.success)
   | summarize failures = countif(success == false), total = count()
   | extend failure_rate = todouble(failures) / total
   | where failure_rate > 0.2
   ```

---

### Task: Refactor Hardcoded Username
**Example**: Update `get_repo_bundle()` to accept username parameter

**Steps**:
1. **Find hardcoded references**:
   ```bash
   # In terminal
   cd api/
   grep -r "yungryce" --include="*.py" | grep -v "# Default" | grep -v "Example"
   ```

2. **Update function signature**:
   ```python
   # Before
   def get_repo_bundle():
       username = "yungryce"
       # ...
   
   # After
   def get_repo_bundle(username: str = None):
       if not username:
           username = os.getenv("DEFAULT_USERNAME", "yungryce")
       # ...
   ```

3. **Update HTTP route** to extract username:
   ```python
   # Before
   @app.route(route="bundles", methods=["GET"])
   def get_repo_bundle_http(req: func.HttpRequest):
       return get_repo_bundle()
   
   # After
   @app.route(route="bundles/{username}", methods=["GET"])
   def get_repo_bundle_http(req: func.HttpRequest):
       username = req.route_params.get('username')
       return get_repo_bundle(username)
   ```

4. **Update frontend API client** (if applicable):
   ```typescript
   // Before
   getUserBundle(): Observable<any> {
       return this.http.get(`${this.apiUrl}/bundles`);
   }
   
   // After
   getUserBundle(username: string): Observable<any> {
       return this.http.get(`${this.apiUrl}/bundles/${username}`);
   }
   ```

5. **Add validation** for username format:
   ```python
   import re
   
   if not username or not re.match(r'^[a-zA-Z0-9-]{1,39}$', username):
       return create_error_response("Invalid username format", 400)
   ```

6. **Update tests** to pass `username` parameter.

---

## Testing Checklist

### Before Submitting a PR
- [ ] **Lint passes**: `pylint api/` or `ng lint` (frontend)
- [ ] **Local tests pass**: `pytest api/` or `ng test` (frontend)
- [ ] **Manual smoke test**: 
  - Backend: `func start` → test endpoints with Postman
  - Frontend: `ng serve` → test in browser
- [ ] **Logs include tenant context**: Check Application Insights or console for `username` field
- [ ] **Documentation updated**: Update relevant `.md` files in `.github/project/`
- [ ] **Feature flag documented**: If adding new behavior, document rollback in `MIGRATION-PLAN.md`

### Integration Testing
```bash
# Example: Test orchestration for multiple users
curl -X POST http://localhost:7071/api/orchestrator_start \
  -H "Content-Type: application/json" \
  -d '{"username": "yungryce", "force_refresh": false}'

curl -X POST http://localhost:7071/api/orchestrator_start \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "force_refresh": false}'

# Verify isolated cache entries
az storage blob list --account-name <storage> --container-name github-cache \
  --query "[?metadata.username=='testuser']"
```

---

## Common Pitfalls & Solutions

### Pitfall 1: Direct Azure SDK Usage
**Problem**: Bypassing `cache_manager` leads to inconsistent caching behavior.

**Solution**: Always use `cache_manager.get()` and `cache_manager.save()`.

**Example**:
```python
# ❌ WRONG
from azure.storage.blob import BlobClient
blob_client = BlobClient.from_connection_string(...)
data = blob_client.download_blob().readall()

# ✅ CORRECT
result = cache_manager.get(cache_key)
data = result.get('data')
```

---

### Pitfall 2: Missing Tenant Context in Logs
**Problem**: Can't filter logs by user when debugging multi-tenant issues.

**Solution**: Use `extra={"username": username}` in all log statements.

**Example**:
```python
# ❌ WRONG
logger.info(f"Fetching repos for {username}")

# ✅ CORRECT
logger.info("Fetching repos", extra={"username": username, "repo_count": len(repos)})
```

---

### Pitfall 3: Breaking Existing Behavior
**Problem**: Refactoring changes behavior without feature flag, causing production issues.

**Solution**: Wrap new logic in feature flag, keep old logic as fallback.

**Example**:
```python
# ❌ WRONG (direct change)
data = fetch_from_graphql(repo)

# ✅ CORRECT (feature-flagged)
use_graphql = os.getenv("ENABLE_GRAPHQL_BATCH_FETCH", "false").lower() == "true"
if use_graphql:
    data = fetch_from_graphql(repo)
else:
    data = fetch_from_rest_api(repo)  # Existing behavior
```

---

### Pitfall 4: Ignoring Fingerprint Mismatches
**Problem**: Using stale cache even when repo changed.

**Solution**: Always validate fingerprints before returning cached data.

**Example**:
```python
# ❌ WRONG (TTL-only check)
if cache_age < 600:
    return cached_data

# ✅ CORRECT (fingerprint check)
current_fp = FingerprintManager.generate_metadata_fingerprint(repo_metadata)
if cached_data.get('fingerprint') == current_fp:
    return cached_data
else:
    return fetch_fresh_data()
```

---

## Performance Tips

### 1. Batch GitHub API Calls
**Before**:
```python
readme = github_api.get_file("README.md")
skills = github_api.get_file("SKILLS-INDEX.md")
arch = github_api.get_file("ARCHITECTURE.md")
# 3 API calls
```

**After** (using GraphQL batching in Phase 3):
```python
files = github_api.get_files_batch(["README.md", "SKILLS-INDEX.md", "ARCHITECTURE.md"])
# 1 API call
```

---

### 2. Parallel Orchestration Activities
**Already implemented** in `repo_context_orchestrator`:
```python
tasks = [context.call_activity('fetch_repo_context_bundle_activity', repo) for repo in stale_repos]
results = yield context.task_all(tasks)  # Runs in parallel
```

**Don't** await tasks sequentially:
```python
# ❌ WRONG (serial execution)
results = []
for repo in stale_repos:
    result = yield context.call_activity('fetch_repo_context_bundle_activity', repo)
    results.append(result)
```

---

### 3. Cache Preloading
For known-frequent queries, preload cache:
```python
# In orchestrator
for repo in top_repos:
    cache_key = cache_manager.generate_cache_key(kind='repo', username=username, repo=repo)
    if cache_manager.get(cache_key)['status'] != 'valid':
        # Preload cache for top repos
        data = fetch_repo_context(username, repo)
        cache_manager.save(cache_key, data, ttl=1800)
```

---

## Debugging Guide

### Step 1: Check Logs in Application Insights
```kusto
traces
| where timestamp > ago(1h)
| where severityLevel >= 3  // Warning or Error
| extend username = tostring(customDimensions.username)
| project timestamp, message, username, severityLevel
| order by timestamp desc
```

### Step 2: Inspect Cache State
```python
# In Python REPL or test script
from config.cache_manager import cache_manager

cache_key = "repos_bundle_context_yungryce"
result = cache_manager.get(cache_key)

print(f"Status: {result['status']}")
print(f"Fingerprint: {result.get('fingerprint')}")
print(f"Last Modified: {result.get('last_modified')}")
print(f"Size: {result.get('size_bytes')} bytes")
```

### Step 3: Trace Orchestration Flow
```bash
# Start orchestration with logging
curl -X POST http://localhost:7071/api/orchestrator_start \
  -H "Content-Type: application/json" \
  -d '{"username": "yungryce", "force_refresh": true}'

# Check orchestration status
curl http://localhost:7071/runtime/webhooks/durabletask/instances/{instance_id}
```

### Step 4: Profile GitHub API Usage
```python
# In github_api.py, add timing decorator
import time
from functools import wraps

def log_duration(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start
        logger.info(f"{func.__name__} took {duration:.2f}s", extra={"duration_sec": duration})
        return result
    return wrapper

@log_duration
def get_file_content(self, repo, path):
    # ... existing logic
```

---

## Useful Commands

### Backend Development
```bash
# Install dependencies
cd api/
pip install -r requirements.txt

# Start local Functions runtime
func start

# Run tests
pytest

# Lint code
pylint **/*.py --disable=C0111,R0913
```

### Frontend Development
```bash
# Install dependencies
npm install

# Start dev server
npm run start  # or ng serve

# Build production
npm run build

# Run tests
npm test  # or ng test
```

### Infrastructure
```bash
# Validate Bicep
az bicep build --file infra/main.bicep

# Deploy infrastructure
cd infra/
./infra-run.sh  # Interactive script

# Check deployment status
az deployment group list -g portfolio-dev --query "[0].properties.provisioningState"
```

### Azure CLI Helpers
```bash
# List cache blobs
az storage blob list \
  --account-name <storage> \
  --container-name github-cache \
  --query "[].{name:name, size:properties.contentLength, modified:properties.lastModified}"

# Download specific cache entry
az storage blob download \
  --account-name <storage> \
  --container-name github-cache \
  --name "repos_bundle_context_yungryce" \
  --file /tmp/bundle.json

# Delete user's cache
az storage blob delete-batch \
  --account-name <storage> \
  --source github-cache \
  --pattern "repos_bundle_context_yungryce*"
```

---

## References

### Primary Docs (Read First)
- [MIGRATION-PLAN.md](./MIGRATION-PLAN.md) - Overall migration strategy
- [CACHE-CONTRACT.md](./CACHE-CONTRACT.md) - Cache API specification
- [MULTI-TENANT-DESIGN.md](./MULTI-TENANT-DESIGN.md) - Tenant isolation patterns

### Code-Specific Docs
- [../copilot-instructions.md](../copilot-instructions.md) - Global coding patterns
- [api/.github/copilot-instructions.md](../../api/.github/copilot-instructions.md) - Backend-specific patterns
- [src/.github/copilot-instructions.md](../../src/.github/copilot-instructions.md) - Frontend-specific patterns

### External Resources
- [Azure Functions Python Developer Guide](https://docs.microsoft.com/en-us/azure/azure-functions/functions-reference-python)
- [Azure Durable Functions Patterns](https://docs.microsoft.com/en-us/azure/azure-functions/durable/durable-functions-overview)
- [Application Insights KQL Reference](https://docs.microsoft.com/en-us/azure/data-explorer/kusto/query/)

---

**Document Owner**: Migration Team  
**Last Updated**: October 7, 2025  
**Feedback**: Submit issues to GitHub Project board with label `docs: improvement`
