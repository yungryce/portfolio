# Queue Migration Implementation Backlog

**Date**: October 12, 2025  
**Status**: Ready for GitHub Projects Import  
**Estimated Timeline**: 4-6 weeks (1 developer)

---

## Epic Structure

```
Epic 1: Infrastructure Setup (Week 1)
  ├─ 6 issues (foundation)
  
Epic 2: API Gateway Service (Week 2)
  ├─ 5 issues (lightweight REST API)
  
Epic 3: Worker Services (Week 3-4)
  ├─ 8 issues (sync, merge, training workers)
  
Epic 4: Migration & Cutover (Week 5)
  ├─ 6 issues (feature flags, monitoring, rollback)
  
Epic 5: Cleanup & Documentation (Week 6)
  ├─ 4 issues (decommission old code, finalize docs)
```

---

## Epic 1: Infrastructure Setup 🏗️

### Issue 1.1: Deploy Redis Message Queue
**Labels**: `infrastructure`, `priority:critical`, `phase:1`  
**Estimate**: 4 hours  
**Milestone**: Week 1

**Description**:
Deploy Azure Cache for Redis to serve as message queue backbone.

**Acceptance Criteria**:
- [ ] Azure Cache for Redis (Basic tier, 1GB) deployed in `westeurope`
- [ ] Connection string stored in Key Vault as `REDIS-URL`
- [ ] VNet integration with private endpoint
- [ ] 3 queues created: `github-sync-queue`, `merge-queue`, `training-queue`
- [ ] Test script confirms RPUSH/BLPOP operations work

**Implementation Notes**:
```bash
# Bicep snippet
resource redis 'Microsoft.Cache/Redis@2023-08-01' = {
  name: 'redis-${suffix}'
  location: location
  properties: {
    sku: { name: 'Basic', capacity: 1 }
    enableNonSslPort: false
  }
}
```

**Reference**: [QUEUE-ARCHITECTURE-PLAN.md § Queue Types](./QUEUE-ARCHITECTURE-PLAN.md#queue-types)

---

### Issue 1.2: Create Container Registry & Base Images
**Labels**: `infrastructure`, `priority:high`, `phase:1`  
**Estimate**: 3 hours  
**Milestone**: Week 1

**Description**:
Set up Azure Container Registry and build base Docker images for workers.

**Acceptance Criteria**:
- [ ] Azure Container Registry deployed with admin enabled
- [ ] Base image `worker-base:latest` with Python 3.11, common deps
- [ ] Image pushed to ACR and pullable by Managed Identity
- [ ] GitHub Actions workflow to rebuild base image on `requirements.txt` changes

**Dockerfile**:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Workers will extend this
```

---

### Issue 1.3: Add Dead Letter Queue Monitoring
**Labels**: `monitoring`, `priority:medium`, `phase:1`  
**Estimate**: 2 hours  
**Milestone**: Week 1

**Description**:
Configure Redis DLQ pattern and Application Insights alerts for failed messages.

**Acceptance Criteria**:
- [ ] DLQ keys: `github-sync-dlq`, `merge-dlq`, `training-dlq`
- [ ] Worker error handler moves failed messages to DLQ after 3 retries
- [ ] Application Insights alert when DLQ depth > 5
- [ ] Dashboard shows DLQ depth by queue type

**Code Pattern**:
```python
def process_with_retry(message, max_retries=3):
    for attempt in range(max_retries):
        try:
            process_message(message)
            return
        except Exception as e:
            if attempt == max_retries - 1:
                redis.rpush(f"{queue_name}-dlq", json.dumps({
                    "message": message,
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }))
                logger.error(f"Moved to DLQ: {e}")
```

---

### Issue 1.4: Abstract Cache Manager for Multi-Cloud
**Labels**: `architecture`, `priority:low`, `phase:1`  
**Estimate**: 4 hours  
**Milestone**: Week 1

**Description**:
Create storage abstraction layer to support Azure Blob → S3 → GCS migration.

**Acceptance Criteria**:
- [ ] New interface `StorageBackend` in `config/storage_backend.py`
- [ ] `AzureBlobBackend` implements interface (existing logic)
- [ ] `cache_manager.py` uses backend via dependency injection
- [ ] Environment variable `STORAGE_BACKEND=azure` (default)
- [ ] Unit tests mock backend for fast testing

**Interface**:
```python
class StorageBackend(ABC):
    @abstractmethod
    def save(self, key: str, data: Any, ttl: int, metadata: dict) -> None:
        pass
    
    @abstractmethod
    def get(self, key: str) -> dict:
        pass
    
    @abstractmethod
    def delete(self, key: str) -> None:
        pass

class AzureBlobBackend(StorageBackend):
    # Existing cache_manager.py logic
```

---

### Issue 1.5: Setup OpenTelemetry Tracing
**Labels**: `monitoring`, `priority:medium`, `phase:1`  
**Estimate**: 3 hours  
**Milestone**: Week 1

**Description**:
Add distributed tracing to track message flow across services.

**Acceptance Criteria**:
- [ ] OpenTelemetry SDK installed in all workers
- [ ] Trace context propagated via Redis message headers
- [ ] Application Insights shows end-to-end traces (API → Worker → Cache)
- [ ] Custom spans: `fetch_repo_content`, `save_to_cache`, `train_model`

**Code**:
```python
from opentelemetry import trace
tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("process_sync_message") as span:
    span.set_attribute("username", username)
    span.set_attribute("repo", repo_name)
    process_sync_message(message)
```

---

### Issue 1.6: Update Bicep for Queue Infrastructure
**Labels**: `infrastructure`, `priority:critical`, `phase:1`  
**Estimate**: 2 hours  
**Milestone**: Week 1

**Description**:
Add Redis, Container Registry, and worker resources to `infra/main.bicep`.

**Acceptance Criteria**:
- [ ] Redis resource with private endpoint
- [ ] Container Registry with Managed Identity access
- [ ] Output variables: `redisUrl`, `acrLoginServer`
- [ ] Deploy script validates all resources created

**Bicep**:
```bicep
resource redis 'Microsoft.Cache/Redis@2023-08-01' = { ... }
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = { ... }

output redisUrl string = redis.properties.hostName
output acrLoginServer string = acr.properties.loginServer
```

---

## Epic 2: API Gateway Service 🌐

### Issue 2.1: Create FastAPI Gateway Skeleton
**Labels**: `backend`, `priority:critical`, `phase:2`  
**Estimate**: 3 hours  
**Milestone**: Week 2

**Description**:
Scaffold FastAPI application with health check and stub endpoints.

**Acceptance Criteria**:
- [ ] New directory `api/gateway/` with `app.py`, `requirements.txt`, `Dockerfile`
- [ ] Health check endpoint `GET /health` returns 200
- [ ] Stub endpoint `POST /bundles/{username}/refresh` returns 501 Not Implemented
- [ ] Docker image builds and runs locally
- [ ] OpenAPI docs accessible at `/docs`

**File Structure**:
```
api/gateway/
├── app.py
├── requirements.txt  (fastapi, uvicorn, redis, azure-storage-blob)
├── Dockerfile
└── tests/
    └── test_health.py
```

---

### Issue 2.2: Implement Bundle Refresh Endpoint
**Labels**: `backend`, `priority:critical`, `phase:2`  
**Estimate**: 5 hours  
**Milestone**: Week 2

**Description**:
Implement `POST /bundles/{username}/refresh` to enqueue sync jobs.

**Acceptance Criteria**:
- [ ] Endpoint checks cache for existing bundle
- [ ] Returns `{status: "cached", ...}` if valid and `force=false`
- [ ] Identifies stale repos via fingerprint comparison
- [ ] Enqueues N messages to `github-sync-queue`
- [ ] Returns `{status: "processing", job_id, ...}` with 202 status
- [ ] Unit tests with mocked Redis and cache

**Code Reference**: [QUEUE-ARCHITECTURE-PLAN.md § API Gateway](./QUEUE-ARCHITECTURE-PLAN.md#service-1-api-gateway-lightweight)

---

### Issue 2.3: Implement Job Status Endpoint
**Labels**: `backend`, `priority:high`, `phase:2`  
**Estimate**: 3 hours  
**Milestone**: Week 2

**Description**:
Add `GET /bundles/{username}/status?job_id={id}` to track progress.

**Acceptance Criteria**:
- [ ] Returns job metadata: `{status, total_repos, completed_repos, created_at}`
- [ ] Status values: `queued`, `processing`, `completed`, `failed`
- [ ] Updates in real-time as workers complete tasks
- [ ] Returns 404 if job_id not found or expired (TTL 1 hour)

**Redis Schema**:
```
Key: job:{uuid}
Type: Hash
Fields:
  - username: yungryce
  - total_repos: 10
  - completed_repos: 7
  - status: processing
  - created_at: 2025-10-12T10:00:00Z
```

---

### Issue 2.4: Deploy Gateway to Azure Container Apps
**Labels**: `infrastructure`, `priority:high`, `phase:2`  
**Estimate**: 4 hours  
**Milestone**: Week 2

**Description**:
Deploy FastAPI gateway with auto-scaling and custom domain.

**Acceptance Criteria**:
- [ ] Azure Container App created with `gateway:latest` image
- [ ] Ingress enabled with HTTPS (Let's Encrypt certificate)
- [ ] Environment variables: `REDIS_URL`, `AZURE_STORAGE_CONNECTION_STRING`
- [ ] Auto-scale rules: 2-5 replicas based on HTTP requests
- [ ] Custom domain `api-queue.yourportfolio.com` (optional)

**Bicep**:
```bicep
resource gatewayApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: 'gateway-${suffix}'
  properties: {
    configuration: {
      ingress: { external: true, targetPort: 8000 }
    }
    template: {
      scale: { minReplicas: 2, maxReplicas: 5 }
      containers: [{
        name: 'gateway'
        image: '${acr.properties.loginServer}/gateway:latest'
      }]
    }
  }
}
```

---

### Issue 2.5: Add Feature Flag for Queue Mode
**Labels**: `backend`, `priority:critical`, `phase:2`  
**Estimate**: 2 hours  
**Milestone**: Week 2

**Description**:
Add toggle in existing Function App to route traffic to queue-based API.

**Acceptance Criteria**:
- [ ] Environment variable `ENABLE_QUEUE_MODE=false` (default)
- [ ] When `true`, `orchestrator_start` calls gateway API instead of orchestrator
- [ ] Log routing decision: `"Using queue-based API (flag enabled)"`
- [ ] Existing tests pass with flag disabled
- [ ] New integration test validates gateway routing

**Code** (in `function_app.py`):
```python
@app.route(route="orchestrator_start", methods=["POST"])
async def http_start(req: func.HttpRequest, client):
    if os.getenv('ENABLE_QUEUE_MODE') == 'true':
        # Route to new gateway
        async with aiohttp.ClientSession() as session:
            response = await session.post(
                f"{GATEWAY_URL}/bundles/{username}/refresh",
                json=req.get_json()
            )
            return create_success_response(await response.json())
    else:
        # Existing Durable Functions path
        instance_id = await client.start_new('repo_context_orchestrator', ...)
```

---

## Epic 3: Worker Services 🤖

### Issue 3.1: Create Sync Worker Base
**Labels**: `backend`, `priority:critical`, `phase:3`  
**Estimate**: 4 hours  
**Milestone**: Week 3

**Description**:
Build containerized sync worker that processes `github-sync-queue` messages.

**Acceptance Criteria**:
- [ ] New directory `api/workers/sync_worker/` with `worker.py`, `Dockerfile`
- [ ] Worker uses BLPOP to consume messages from Redis
- [ ] Graceful shutdown on SIGTERM (drain current message)
- [ ] Health check: last processed message timestamp
- [ ] Docker image builds and runs locally with `docker-compose`

**Code Structure**:
```python
def main():
    logger.info("Sync Worker started")
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    while not shutdown_requested:
        try:
            _, message_raw = redis.blpop("github-sync-queue", timeout=5)
            if message_raw:
                process_sync_message(json.loads(message_raw))
        except Exception as e:
            logger.error(f"Worker error: {e}", exc_info=True)
```

---

### Issue 3.2: Implement Sync Message Processing
**Labels**: `backend`, `priority:critical`, `phase:3`  
**Estimate**: 5 hours  
**Milestone**: Week 3

**Description**:
Port `fetch_repo_context_bundle_activity` logic into sync worker.

**Acceptance Criteria**:
- [ ] Fetches `.repo-context.json`, README, SKILLS-INDEX, ARCHITECTURE
- [ ] Computes file types using `FileTypeAnalyzer`
- [ ] Saves to per-repo cache with fingerprint
- [ ] Increments job progress in Redis: `HINCRBY job:{id} completed_repos 1`
- [ ] Triggers merge job when all repos synced
- [ ] Unit tests with mocked GitHub API

**Shared Code**:
- Extract fetch logic to `config/repo_fetcher.py` (reusable by Function App)
- Both Durable activity and worker import same module

---

### Issue 3.3: Deploy Sync Worker with Auto-Scaling
**Labels**: `infrastructure`, `priority:high`, `phase:3`  
**Estimate**: 4 hours  
**Milestone**: Week 3

**Description**:
Deploy sync worker to Azure Container Apps with queue-based scaling.

**Acceptance Criteria**:
- [ ] Container App with `sync-worker:latest` image
- [ ] KEDA scale rule: scale 2-20 replicas based on `github-sync-queue` depth
- [ ] Trigger: Add 1 replica per 10 messages in queue
- [ ] Environment variables: `REDIS_URL`, `GITHUB_TOKEN`
- [ ] Managed Identity for cache access (no connection strings in code)

**KEDA Rule**:
```yaml
scale:
  minReplicas: 2
  maxReplicas: 20
  rules:
    - name: redis-queue-depth
      type: redis
      metadata:
        address: ${REDIS_URL}
        listName: github-sync-queue
        listLength: '10'
```

---

### Issue 3.4: Create Merge Worker
**Labels**: `backend`, `priority:high`, `phase:3`  
**Estimate**: 4 hours  
**Milestone**: Week 3

**Description**:
Build worker to aggregate per-repo caches into bundle.

**Acceptance Criteria**:
- [ ] Consumes messages from `merge-queue`
- [ ] Loads all per-repo caches for username
- [ ] Computes bundle fingerprint
- [ ] Saves merged bundle to cache
- [ ] Updates job status to `completed`
- [ ] Enqueues training job to `training-queue`

**Code Reference**: [QUEUE-ARCHITECTURE-PLAN.md § Merge Worker](./QUEUE-ARCHITECTURE-PLAN.md#service-3-merge-worker-lightweight-aggregation)

---

### Issue 3.5: Optimize Merge Worker for Large Bundles
**Labels**: `performance`, `priority:medium`, `phase:3`  
**Estimate**: 3 hours  
**Milestone**: Week 3

**Description**:
Add pagination and streaming for users with 100+ repositories.

**Acceptance Criteria**:
- [ ] Fetches repos in batches of 50 to avoid memory spike
- [ ] Streams bundle to Blob Storage (no in-memory accumulation)
- [ ] Handles bundle fingerprint incrementally (hash per batch)
- [ ] Load test with 200 repos completes in < 30s

**Optimization**:
```python
def merge_in_batches(username, batch_size=50):
    repo_manager = GitHubRepoManager(username)
    all_repos = repo_manager.get_all_repos_metadata()
    
    fingerprints = []
    for i in range(0, len(all_repos), batch_size):
        batch = all_repos[i:i+batch_size]
        for repo in batch:
            # Load and stream to bundle
            fingerprints.append(repo['fingerprint'])
    
    bundle_fp = generate_bundle_fingerprint(fingerprints)
```

---

### Issue 3.6: Create Training Worker
**Labels**: `backend`, `priority:medium`, `phase:3`  
**Estimate**: 5 hours  
**Milestone**: Week 4

**Description**:
Extract model training into isolated worker with GPU support.

**Acceptance Criteria**:
- [ ] Consumes messages from `training-queue`
- [ ] Checks if model already cached for fingerprint (skip if exists)
- [ ] Loads documented repos from bundle
- [ ] Calls `SemanticModel.fine_tune_model()` (existing logic)
- [ ] Saves trained model to cache
- [ ] Handles training failures gracefully (DLQ after 1 retry)

**Dockerfile**:
```dockerfile
FROM worker-base:latest
# Add PyTorch CPU-only to reduce image size
RUN pip install torch==2.2.2+cpu sentence-transformers==2.6.1 -f https://download.pytorch.org/whl/torch_stable.html
COPY training_worker.py .
CMD ["python", "training_worker.py"]
```

---

### Issue 3.7: Deploy Training Worker with Scale-to-Zero
**Labels**: `infrastructure`, `priority:medium`, `phase:3`  
**Estimate**: 4 hours  
**Milestone**: Week 4

**Description**:
Deploy training worker to Azure Container Instances (ACI) with on-demand provisioning.

**Acceptance Criteria**:
- [ ] Azure Container Instance with `training-worker:latest` image
- [ ] CPU-optimized SKU (2 vCPU, 4 GB RAM)
- [ ] Provision only when `training-queue` has messages (Logic App trigger)
- [ ] Auto-delete after queue empty for 10 minutes
- [ ] Cost < $2/training run

**Logic App Flow**:
```
Trigger: Check Redis queue depth every 5 minutes
Condition: If queue > 0 AND no running ACI
Action: Create ACI instance
Wait: Until queue empty
Action: Delete ACI instance
```

---

### Issue 3.8: Add Worker Health Checks & Monitoring
**Labels**: `monitoring`, `priority:high`, `phase:3`  
**Estimate**: 3 hours  
**Milestone**: Week 4

**Description**:
Implement liveness probes and worker-specific metrics.

**Acceptance Criteria**:
- [ ] Each worker exposes `/health` endpoint (HTTP server on port 8080)
- [ ] Health check criteria: last processed message < 60s ago
- [ ] Container Apps restart worker if unhealthy for 3 consecutive checks
- [ ] Custom metrics: `messages_processed_total`, `processing_duration_seconds`
- [ ] Application Insights dashboard: worker throughput by type

**Health Check**:
```python
from flask import Flask
health_app = Flask(__name__)
last_processed = datetime.utcnow()

@health_app.route('/health')
def health():
    if (datetime.utcnow() - last_processed).seconds < 60:
        return {"status": "healthy"}, 200
    else:
        return {"status": "unhealthy", "reason": "no recent messages"}, 503
```

---

## Epic 4: Migration & Cutover 🚀

### Issue 4.1: Implement Shadow Mode Testing
**Labels**: `testing`, `priority:critical`, `phase:4`  
**Estimate**: 4 hours  
**Milestone**: Week 5

**Description**:
Dual-write to both Durable Functions and queue-based API, compare results.

**Acceptance Criteria**:
- [ ] Feature flag `ENABLE_QUEUE_SHADOW=false` (default)
- [ ] When `true`, both systems process same request (fire-and-forget to queue API)
- [ ] Log comparison: latency, cache consistency, error rates
- [ ] Alert if cache fingerprints differ between systems
- [ ] Run shadow mode for 48 hours with production traffic

**Code**:
```python
# In function_app.py
if os.getenv('ENABLE_QUEUE_SHADOW') == 'true':
    # Fire-and-forget to new API (don't wait for response)
    asyncio.create_task(shadow_call_queue_api(username))

# Original Durable Functions path continues
instance_id = await client.start_new('repo_context_orchestrator', username)
```

---

### Issue 4.2: Create Gradual Rollout Mechanism
**Labels**: `deployment`, `priority:critical`, `phase:4`  
**Estimate**: 3 hours  
**Milestone**: Week 5

**Description**:
Implement percentage-based traffic routing to queue-based API.

**Acceptance Criteria**:
- [ ] Environment variable `QUEUE_TRAFFIC_PCT=0` (default)
- [ ] Random routing: `if random.randint(1,100) <= PCT: use_queue_api()`
- [ ] Log routing decision with user and percentage
- [ ] Set `QUEUE_TRAFFIC_PCT=10` → monitor for 24h → `50` → `100`
- [ ] Rollback plan: Set to `0` in Key Vault (no redeploy needed)

---

### Issue 4.3: Add Error Rate Monitoring & Auto-Rollback
**Labels**: `monitoring`, `priority:high`, `phase:4`  
**Estimate**: 4 hours  
**Milestone**: Week 5

**Description**:
Automatic rollback if queue-based API error rate exceeds threshold.

**Acceptance Criteria**:
- [ ] Application Insights alert: error rate > 2% for 5 minutes
- [ ] Webhook triggers Azure Automation runbook
- [ ] Runbook sets `QUEUE_TRAFFIC_PCT=0` in Key Vault
- [ ] Notification sent to Slack/Teams
- [ ] Manual re-enable after root cause fixed

**KQL Query**:
```kusto
requests
| where timestamp > ago(5m)
| where customDimensions.routing_mode == "queue"
| summarize
    total = count(),
    errors = countif(resultCode >= 400)
| extend error_rate = errors * 100.0 / total
| where error_rate > 2.0
```

---

### Issue 4.4: Performance Load Testing
**Labels**: `testing`, `priority:high`, `phase:4`  
**Estimate**: 5 hours  
**Milestone**: Week 5

**Description**:
Validate queue-based system handles 10× current load without degradation.

**Acceptance Criteria**:
- [ ] Locust/K6 script simulates 100 concurrent users
- [ ] Test scenario: 50% cache hits, 30% partial refresh, 20% full refresh
- [ ] Measure: P50, P95, P99 latency; error rate < 0.1%
- [ ] Verify workers auto-scale from 2 → 20 replicas
- [ ] Results documented in `docs/LOAD-TEST-RESULTS.md`

**Locust Script**:
```python
from locust import HttpUser, task

class PortfolioUser(HttpUser):
    @task(50)
    def get_cached_bundle(self):
        self.client.get("/bundles/yungryce")
    
    @task(30)
    def refresh_bundle(self):
        self.client.post("/bundles/yungryce/refresh", json={"force": False})
    
    @task(20)
    def force_refresh(self):
        self.client.post("/bundles/yungryce/refresh", json={"force": True})
```

---

### Issue 4.5: Update Frontend to Poll Job Status
**Labels**: `frontend`, `priority:medium`, `phase:4`  
**Estimate**: 4 hours  
**Milestone**: Week 5

**Description**:
Modify Angular `RepoBundleService` to handle async job completion.

**Acceptance Criteria**:
- [ ] If API returns `{status: "processing", job_id}`, poll status endpoint every 2s
- [ ] Show progress bar: `completed_repos / total_repos`
- [ ] Display spinner: "Syncing 7 of 10 repositories..."
- [ ] Auto-refresh bundle when status changes to `completed`
- [ ] Timeout after 5 minutes with retry option

**Angular Service**:
```typescript
refreshBundle(username: string): Observable<Bundle> {
  return this.http.post(`/bundles/${username}/refresh`, {}).pipe(
    switchMap(resp => {
      if (resp.status === 'cached') {
        return of(resp.data);
      } else {
        // Poll status until completed
        return interval(2000).pipe(
          switchMap(() => this.http.get(`/bundles/${username}/status?job_id=${resp.job_id}`)),
          filter(status => status.status === 'completed'),
          take(1),
          switchMap(() => this.http.get(`/bundles/${username}`))
        );
      }
    })
  );
}
```

---

### Issue 4.6: Document Rollback Procedures
**Labels**: `documentation`, `priority:critical`, `phase:4`  
**Estimate**: 2 hours  
**Milestone**: Week 5

**Description**:
Create runbook for reverting to Durable Functions in case of failure.

**Acceptance Criteria**:
- [ ] Document in `.github/plans/ROLLBACK-PLAYBOOK.md`
- [ ] Step-by-step: disable flags, verify logs, restart Function App
- [ ] Include rollback decision criteria (error rate, latency)
- [ ] Pre-filled commands with placeholders for subscription/resource group
- [ ] Tested in staging environment

**Sample Rollback**:
```bash
# 1. Disable queue routing (immediate)
az keyvault secret set --name "QUEUE-TRAFFIC-PCT" --value "0"

# 2. Verify Function App picks up change (< 5 min)
az monitor app-insights query --app $APP_INSIGHTS --analytics-query "requests | where customDimensions.routing_mode == 'durable'"

# 3. If errors persist, restart Function App
az functionapp restart --name $FUNCTION_APP_NAME --resource-group $RG
```

---

## Epic 5: Cleanup & Documentation 📚

### Issue 5.1: Remove Durable Functions Orchestrator
**Labels**: `cleanup`, `priority:medium`, `phase:5`  
**Estimate**: 3 hours  
**Milestone**: Week 6

**Description**:
Delete orchestrator and activity functions after 100% traffic on queue-based API.

**Acceptance Criteria**:
- [ ] Verify `QUEUE_TRAFFIC_PCT=100` stable for 7 days
- [ ] Delete `repo_context_orchestrator`, `get_stale_repos_activity`, `fetch_repo_context_bundle_activity`, `merge_repo_results_activity`, `train_semantic_model_activity`
- [ ] Remove Durable Functions storage queues and state tables
- [ ] Update `requirements.txt`: remove `azure-functions-durable`
- [ ] All tests pass without Durable Functions dependencies

---

### Issue 5.2: Simplify Infrastructure (Remove Flex Plan)
**Labels**: `infrastructure`, `priority:low`, `phase:5`  
**Estimate**: 2 hours  
**Milestone**: Week 6

**Description**:
Remove Azure Functions Flex Consumption plan, migrate remaining endpoints to Container Apps.

**Acceptance Criteria**:
- [ ] Remaining Function App endpoints (`/ai`, `/health`) migrated to gateway
- [ ] Delete `appServicePlan` resource from Bicep
- [ ] Update DNS: point `api.yourportfolio.com` → Container Apps gateway
- [ ] Cost reduction: ~$50/month

**Bicep Diff**:
```diff
- resource appServicePlan 'Microsoft.Web/serverfarms@2024-11-01' = { ... }
- resource functionApp 'Microsoft.Web/sites@2024-11-01' = { ... }
```

---

### Issue 5.3: Update All Documentation
**Labels**: `documentation`, `priority:high`, `phase:5`  
**Estimate**: 4 hours  
**Milestone**: Week 6

**Description**:
Revise project docs to reflect queue-based architecture.

**Acceptance Criteria**:
- [ ] Update `.github/copilot-instructions.md`: new file structure, worker patterns
- [ ] Update `api/README.md`: remove Durable Functions, add worker deployment
- [ ] Create `api/workers/README.md`: worker development guide
- [ ] Update `ARCHITECTURE.md`: new architecture diagram (mermaid)
- [ ] Archive `.github/project/MIGRATION-PLAN.md` (mark as completed)

---

### Issue 5.4: Create Developer Onboarding Guide
**Labels**: `documentation`, `priority:medium`, `phase:5`  
**Estimate**: 3 hours  
**Milestone**: Week 6

**Description**:
Write guide for new developers to run queue-based system locally.

**Acceptance Criteria**:
- [ ] Document in `docs/LOCAL-DEVELOPMENT.md`
- [ ] Docker Compose file with: Redis, gateway, sync worker, merge worker
- [ ] One-command startup: `docker-compose up`
- [ ] Mock GitHub API responses for offline development
- [ ] Troubleshooting section: common Redis connection issues

**Docker Compose**:
```yaml
version: '3.8'
services:
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
  
  gateway:
    build: ./api/gateway
    ports: ["8000:8000"]
    environment:
      REDIS_URL: redis://redis:6379
  
  sync-worker:
    build: ./api/workers/sync_worker
    environment:
      REDIS_URL: redis://redis:6379
      GITHUB_TOKEN: ${GITHUB_TOKEN}
```

---

## Issue Templates

### Feature Issue Template
```markdown
**Epic**: [Epic Name]  
**Priority**: [Critical/High/Medium/Low]  
**Estimate**: X hours  

### Description
[Clear description of what needs to be built]

### Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

### Implementation Notes
[Code snippets, architecture decisions]

### Testing
- [ ] Unit tests
- [ ] Integration tests
- [ ] Manual testing steps

### Documentation
- [ ] Update relevant docs
- [ ] Add inline code comments
```

---

## Labels Schema

```yaml
# Priority
priority:critical  # Blocks other work
priority:high      # Important but not blocking
priority:medium    # Nice to have
priority:low       # Can be deferred

# Phase
phase:1  # Infrastructure
phase:2  # API Gateway
phase:3  # Workers
phase:4  # Migration
phase:5  # Cleanup

# Type
type:feature       # New functionality
type:bug           # Fixes broken behavior
type:docs          # Documentation only
type:refactor      # Code cleanup

# Component
component:gateway
component:worker
component:infrastructure
component:monitoring
```

---

## Definition of Done (DoD)

All issues must satisfy:
- [ ] Code reviewed by at least 1 peer
- [ ] Unit tests written (>80% coverage for new code)
- [ ] Integration tests pass in staging
- [ ] Documentation updated (inline + external)
- [ ] Deployed to staging and smoke tested
- [ ] Application Insights alerts configured (if applicable)
- [ ] Performance benchmarked (if latency-critical)

---

## Milestones

| Milestone | Target Date | Issues | Success Metric |
|-----------|-------------|--------|----------------|
| Week 1: Infrastructure Ready | Oct 19 | 1.1-1.6 | Redis deployed, workers can connect |
| Week 2: Gateway Deployed | Oct 26 | 2.1-2.5 | `/bundles/{user}/refresh` returns 202 |
| Week 3: Sync Worker Live | Nov 2 | 3.1-3.3 | Workers process messages in parallel |
| Week 4: All Workers Deployed | Nov 9 | 3.4-3.8 | End-to-end flow (API → Workers → Cache) works |
| Week 5: 100% Traffic Cutover | Nov 16 | 4.1-4.6 | All users on queue-based system |
| Week 6: Cleanup Complete | Nov 23 | 5.1-5.4 | Durable Functions code deleted |

---

## Risk Register

| Risk | Mitigation | Owner |
|------|------------|-------|
| Redis outage causes data loss | Use persistent queues, DLQ for retries | DevOps |
| Worker autoscaling too slow | Pre-warm 2 workers, tune KEDA thresholds | Backend |
| Cache inconsistency during migration | Fingerprint validation, atomic bundle updates | Backend |
| Training worker GPU cost overrun | Use CPU-only, optimize batch size, scale-to-zero | Backend |
| Frontend polling hammers API | Implement exponential backoff, max 30s poll | Frontend |

---

**Status**: Ready for import into GitHub Projects  
**Next Action**: Create project board, import issues, assign to developers
