# Multi-Tenant Design Guide

**Version**: 1.0  
**Status**: Preparation Phase (Not Yet Enforced)  
**Goal**: Design all services with tenant isolation patterns from day one

---

## Overview

CloudFolio is currently a single-user (canary) application with `yungryce` as the primary user. This document outlines how to prepare the codebase for **multi-tenant operation** without breaking existing functionality.

### Key Principles
1. **Username as Tenant ID**: Use GitHub username as the primary tenant identifier
2. **No Hardcoded Defaults**: All services accept `username` as a parameter
3. **Tenant Context in Logs**: Every log entry includes tenant identifier for debugging
4. **Quota Preparation**: Soft limits (warnings) now, enforcement later
5. **Graceful Degradation**: Single-user mode remains default until multi-tenant enabled

---

## Tenant Identification

### Primary Identifier: GitHub Username
- **Format**: Alphanumeric string, 1-39 characters (GitHub's limit)
- **Example**: `yungryce`, `testuser`, `microsoft`
- **Validation**: Regex `^[a-zA-Z0-9-]{1,39}$`

### Default Behavior (Current)
```python
# ❌ BAD: Hardcoded default
username = "yungryce"

# ✅ GOOD: Accept as parameter with fallback
def get_user_bundle(username: str = None):
    if not username:
        username = os.getenv("DEFAULT_USERNAME", "yungryce")
    # ... rest of logic
```

### API Request Pattern
All HTTP endpoints must accept `username` in:
1. **Path parameter**: `/api/bundles/{username}`
2. **Query parameter**: `/api/bundles?username={username}`
3. **Request body**: `{"username": "yungryce", "query": "..."}`

---

## Tenant Isolation Patterns

### 1. Cache Isolation

**Current**: Single blob container with username-prefixed keys
```python
# Bundle cache key
key = f"repos_bundle_context_{username}"

# Per-repo cache key
key = f"repo_context_{username}_{repo}"
```

**Metadata Tagging**:
```python
# When saving to cache
blob_metadata = {
    "username": username,
    "created_at": datetime.now().isoformat(),
    "cache_version": "1.0"
}
cache_manager.save(key, data, ttl=600, metadata=blob_metadata)
```

**Quota Tracking** (Phase 4):
```python
def get_user_cache_size(username: str) -> int:
    """Returns total cache size in bytes for a user."""
    total = 0
    for blob in cache_manager.list_blobs():
        if blob.metadata.get("username") == username:
            total += blob.size
    return total
```

---

### 2. Log Context Isolation

**Structured Logging**: Include tenant context in all log entries

**Example**:
```python
import logging
logger = logging.getLogger('portfolio.api')

# ❌ BAD: No tenant context
logger.info("Processing 10 repositories")

# ✅ GOOD: Include tenant context
logger.info(
    "Processing repositories", 
    extra={
        "username": username,
        "repo_count": 10,
        "operation": "orchestration"
    }
)
```

**Application Insights Query**:
```kusto
traces
| where timestamp > ago(1h)
| extend username = tostring(customDimensions.username)
| summarize count() by username, operation_Name
| order by count_ desc
```

---

### 3. Rate Limiting & Quotas

**Soft Limits** (Phase 4): Log warnings, don't block

```python
# In api/config/quota_manager.py (to be created)
class QuotaManager:
    LIMITS = {
        "cache_storage_mb": 100,
        "orchestrations_per_day": 50,
        "model_trainings_per_week": 2
    }
    
    def check_quota(self, username: str, resource: str) -> dict:
        current_usage = self._get_usage(username, resource)
        limit = self.LIMITS.get(resource, float('inf'))
        
        if current_usage >= limit:
            logger.warning(
                f"User {username} exceeds {resource} quota",
                extra={
                    "username": username,
                    "resource": resource,
                    "current": current_usage,
                    "limit": limit
                }
            )
            # Don't block yet, just warn
        
        return {
            "resource": resource,
            "current": current_usage,
            "limit": limit,
            "exceeded": current_usage >= limit
        }
```

**Usage Tracking**:
```python
# Track orchestration runs per user
from azure.data.tables import TableServiceClient

def increment_orchestration_count(username: str):
    table_client = TableServiceClient.from_connection_string(conn_str).get_table_client("usage_tracking")
    
    date_key = datetime.now().strftime("%Y-%m-%d")
    entity = {
        "PartitionKey": username,
        "RowKey": date_key,
        "orchestration_count": 1  # Increment if exists
    }
    
    try:
        table_client.upsert_entity(entity, mode="merge")
    except Exception as e:
        logger.error(f"Failed to track usage for {username}: {e}")
```

---

### 4. GitHub API Quota Isolation

**Per-User Token** (Future Enhancement):
```python
# Current: Single shared GitHub token
github_token = os.getenv("GITHUB_TOKEN")

# Future: Per-user OAuth tokens
def get_github_token(username: str) -> str:
    # Fetch user's personal access token from Key Vault
    token = key_vault_client.get_secret(f"github-token-{username}")
    return token.value
```

**Rate Limit Tracking**:
```python
# In config/github_api.py
def check_rate_limit(self, username: str):
    response = self.session.get("https://api.github.com/rate_limit")
    data = response.json()
    
    remaining = data["resources"]["core"]["remaining"]
    reset_time = datetime.fromtimestamp(data["resources"]["core"]["reset"])
    
    logger.info(
        "GitHub rate limit check",
        extra={
            "username": username,
            "remaining": remaining,
            "reset_time": reset_time.isoformat()
        }
    )
    
    if remaining < 100:
        logger.warning(f"Low GitHub API quota for {username}: {remaining} remaining")
```

---

## Configuration Management

### Environment Variables (Multi-Tenant Prep)

**Current** (Single-Tenant):
```bash
GITHUB_TOKEN=ghp_xxxxxxxxxxxxx
DEFAULT_USERNAME=yungryce
GROQ_API_KEY=gsk_xxxxxxxxxxxxxx
```

**Future** (Multi-Tenant):
```bash
# Shared service credentials
GROQ_API_KEY=gsk_xxxxxxxxxxxxxx
AZURE_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# Per-user tokens in Key Vault
# github-token-yungryce → ghp_xxx
# github-token-testuser → ghp_yyy
```

### Feature Flags for Multi-Tenant Features

**Recommended Flags** (in Azure App Configuration):
```json
{
  "enable_multi_tenant": false,           // Global toggle
  "enable_quota_enforcement": false,      // Hard limits vs. warnings
  "enable_per_user_github_tokens": false, // Use per-user OAuth vs. shared token
  "default_username": "yungryce"          // Fallback for backward compatibility
}
```

**Usage in Code**:
```python
from azure.appconfiguration import AzureAppConfigurationClient

def is_multi_tenant_enabled() -> bool:
    config_client = AzureAppConfigurationClient.from_connection_string(conn_str)
    setting = config_client.get_configuration_setting(key="enable_multi_tenant")
    return setting.value.lower() == "true"
```

---

## API Contract Changes

### HTTP Endpoint Updates

#### Before (Hardcoded Username)
```python
@app.route(route="bundles", methods=["GET"])
def get_repo_bundle(req: func.HttpRequest) -> func.HttpResponse:
    username = "yungryce"  # ❌ Hardcoded
    bundle = cache_manager.get(f"repos_bundle_context_{username}")
    return create_success_response(bundle)
```

#### After (Username from Request)
```python
@app.route(route="bundles/{username}", methods=["GET"])
def get_repo_bundle(req: func.HttpRequest) -> func.HttpResponse:
    username = req.route_params.get('username')
    
    # Validation
    if not username or not re.match(r'^[a-zA-Z0-9-]{1,39}$', username):
        return create_error_response("Invalid username", 400)
    
    # Tenant context logging
    logger.info("Fetching bundle", extra={"username": username})
    
    bundle = cache_manager.get(f"repos_bundle_context_{username}")
    
    if bundle['status'] != 'valid':
        return create_error_response(f"No data for user {username}", 404)
    
    return create_success_response(bundle['data'])
```

---

## Security Considerations

### 1. Cross-Tenant Data Leakage Prevention

**Validation**: Always validate `username` matches the authenticated user (future OAuth)

```python
def validate_tenant_access(requested_username: str, authenticated_user: str) -> bool:
    """Ensure users can only access their own data."""
    if requested_username != authenticated_user:
        logger.warning(
            "Cross-tenant access attempt blocked",
            extra={
                "requested": requested_username,
                "authenticated": authenticated_user
            }
        )
        return False
    return True
```

### 2. Resource Exhaustion Prevention

**Prevent Single User from Consuming All Resources**:
- Enforce cache storage quotas (100MB per user)
- Limit concurrent orchestrations (5 per user)
- Throttle model training (1 per week per user)

### 3. Sensitive Data Isolation

**GitHub Tokens**:
- Current: Shared token in environment variable
- Future: Per-user tokens in Azure Key Vault with RBAC

**Cache Encryption**:
- Blob storage uses encryption at rest (default)
- No PII stored in cache (only public GitHub data)

---

## Migration Path to Multi-Tenant

### Phase 0: Audit (Week 1)
- [ ] Search codebase for hardcoded `yungryce`
- [ ] Identify all functions missing `username` parameter
- [ ] Document all API endpoints lacking tenant routing

### Phase 1: Parameterize (Week 2-3)
- [ ] Add `username` parameter to all functions
- [ ] Update HTTP routes to accept `username`
- [ ] Refactor cache keys to include `{username}` prefix

### Phase 2: Logging (Week 4)
- [ ] Add tenant context to all log statements
- [ ] Create Application Insights queries for per-user metrics
- [ ] Build admin dashboard showing per-user usage

### Phase 3: Soft Quotas (Week 5)
- [ ] Implement quota tracking (logs only, no enforcement)
- [ ] Add warning thresholds to monitoring
- [ ] Document quota policies for future enforcement

### Phase 4: Authentication (Future)
- [ ] Integrate Azure AD B2C for user authentication
- [ ] Migrate to per-user GitHub OAuth tokens
- [ ] Enable hard quota enforcement

---

## Testing Strategy

### Unit Tests
```python
def test_cache_isolation():
    # User 1 saves data
    cache_manager.save("repos_bundle_context_user1", {"repos": ["repo1"]})
    
    # User 2 saves different data
    cache_manager.save("repos_bundle_context_user2", {"repos": ["repo2"]})
    
    # Verify isolation
    user1_data = cache_manager.get("repos_bundle_context_user1")
    user2_data = cache_manager.get("repos_bundle_context_user2")
    
    assert user1_data['data'] != user2_data['data']
```

### Integration Tests
```python
def test_multi_user_orchestration():
    # Trigger orchestration for two users in parallel
    client.start_orchestration("user1")
    client.start_orchestration("user2")
    
    # Wait for both to complete
    user1_result = client.wait_for_orchestration("user1", timeout=60)
    user2_result = client.wait_for_orchestration("user2", timeout=60)
    
    # Verify results are isolated
    assert user1_result['username'] == "user1"
    assert user2_result['username'] == "user2"
    assert user1_result['data'] != user2_result['data']
```

---

## Admin Operations

### View User List
```kusto
// Application Insights query
requests
| where timestamp > ago(7d)
| extend username = tostring(customDimensions.username)
| summarize 
    requests = count(),
    last_activity = max(timestamp)
    by username
| where username != ""
| order by requests desc
```

### Clear User Cache
```bash
# Azure CLI script
az storage blob delete-batch \
  --account-name portfoliostgXXXX \
  --source github-cache \
  --pattern "repos_bundle_context_${USERNAME}*" \
  --delete-snapshots include
```

### Check User Quota Status
```python
# Admin API endpoint (to be created)
@app.route(route="admin/quota/{username}", methods=["GET"])
def get_user_quota_status(req: func.HttpRequest) -> func.HttpResponse:
    username = req.route_params.get('username')
    
    quota_status = {
        "username": username,
        "cache_storage_mb": get_user_cache_size(username) / 1024 / 1024,
        "cache_limit_mb": 100,
        "orchestrations_today": get_orchestration_count(username, days=1),
        "orchestration_limit": 50,
        "model_trainings_this_week": get_training_count(username, days=7),
        "training_limit": 2
    }
    
    return create_success_response(quota_status)
```

---

## Monitoring & Alerting

### Key Metrics (Per User)
- **Cache Hit Rate**: Should be >80% per user
- **Orchestration Duration**: p95 < 60 seconds per user
- **GitHub API Quota**: Remaining > 1000 per shared token
- **Storage Usage**: Total cache size per user

### Alert Rules
```kusto
// Alert if any user exceeds cache quota
let threshold_mb = 100;
requests
| where timestamp > ago(1h)
| extend username = tostring(customDimensions.username)
| extend cache_size_mb = todouble(customDimensions.cache_size_bytes) / 1024 / 1024
| summarize max_cache_mb = max(cache_size_mb) by username
| where max_cache_mb > threshold_mb
```

---

## References

- Cache Contract: [CACHE-CONTRACT.md](./CACHE-CONTRACT.md)
- Migration Plan: [MIGRATION-PLAN.md](./MIGRATION-PLAN.md)
- Logging Best Practices: [Application Insights Structured Logging](https://docs.microsoft.com/en-us/azure/azure-monitor/app/custom-operations-tracking)

---

**Document Owner**: Architecture Team  
**Last Updated**: October 7, 2025  
**Next Review**: End of Phase 4 (Multi-Tenant Preparation)
