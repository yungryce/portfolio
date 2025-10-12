# Rollback Playbook: Queue-Based Architecture

**Version**: 1.0  
**Last Updated**: October 12, 2025  
**Status**: Active during migration (Weeks 1-5)

---

## Overview

This playbook provides step-by-step procedures to revert from the queue-based microservice architecture back to the original Durable Functions orchestrator in case of critical issues.

**When to Rollback**:
- API error rate > 5% for 10+ minutes
- Queue depth growing unbounded (> 1000 messages)
- Cache corruption detected (fingerprint mismatches)
- Training worker continuously failing (DLQ > 20)
- P95 latency > 30s (worse than original system)

---

## Rollback Levels

### Level 1: Traffic Shift (Immediate, < 2 minutes)
**Impact**: Routes traffic back to Durable Functions without code changes  
**Downtime**: None  
**Data Loss**: No (cache preserved)

### Level 2: Service Disable (< 10 minutes)
**Impact**: Stops all worker services, purges queues  
**Downtime**: 2-5 minutes (cache lookup only)  
**Data Loss**: In-flight messages lost (acceptable)

### Level 3: Full Revert (< 30 minutes)
**Impact**: Deletes queue infrastructure, restores pre-migration state  
**Downtime**: 10-15 minutes  
**Data Loss**: Queue state lost, cache preserved

---

## Pre-Rollback Checklist

Before executing rollback, capture diagnostics:

```bash
# 1. Export current traffic percentage
CURRENT_PCT=$(az keyvault secret show --vault-name $KV_NAME --name "QUEUE-TRAFFIC-PCT" --query value -o tsv)
echo "Current queue traffic: $CURRENT_PCT%"

# 2. Check queue depths
redis-cli -h $REDIS_HOST LLEN github-sync-queue
redis-cli -h $REDIS_HOST LLEN merge-queue
redis-cli -h $REDIS_HOST LLEN training-queue

# 3. Export Application Insights errors (last 15 minutes)
az monitor app-insights query \
  --app $APP_INSIGHTS_NAME \
  --analytics-query "exceptions | where timestamp > ago(15m) | project timestamp, message, outerMessage" \
  --output table > /tmp/rollback-errors.log

# 4. Check worker health
az containerapp list --resource-group $RG --query "[].{Name:name, Status:properties.runningStatus}" -o table

# 5. Verify cache integrity
curl -s "$GATEWAY_URL/bundles/yungryce" | jq '.data | length'
```

**Save diagnostics**:
```bash
# Create incident report directory
mkdir -p ~/rollback-$(date +%Y%m%d-%H%M)
mv /tmp/rollback-errors.log ~/rollback-$(date +%Y%m%d-%H%M)/
```

---

## Level 1: Traffic Shift (Immediate)

### Step 1.1: Disable Queue Routing (< 30 seconds)
```bash
# Set traffic percentage to 0 (all traffic to Durable Functions)
az keyvault secret set \
  --vault-name $KV_NAME \
  --name "QUEUE-TRAFFIC-PCT" \
  --value "0"

echo "✓ Queue traffic disabled. Function App will pick up change within 5 minutes (Key Vault refresh)."
```

**Verification** (wait 2-5 minutes):
```bash
# Check that Function App is routing to Durable Functions
az monitor app-insights query \
  --app $APP_INSIGHTS_NAME \
  --analytics-query "requests | where timestamp > ago(5m) | where name == 'orchestrator_start' | extend routing = tostring(customDimensions.routing_mode) | summarize count() by routing" \
  --output table

# Expected output:
# routing        count
# durable        100
# queue          0
```

---

### Step 1.2: Monitor for Stabilization (5 minutes)
```bash
# Watch error rate in real-time
watch -n 10 'az monitor app-insights query \
  --app $APP_INSIGHTS_NAME \
  --analytics-query "requests | where timestamp > ago(5m) | summarize total=count(), errors=countif(resultCode >= 400) | extend error_rate = errors * 100.0 / total" \
  --output table'

# Target: error_rate < 1%
```

**If errors persist** → Proceed to Level 2

**If errors resolved** → Investigate root cause before re-enabling queues

---

## Level 2: Service Disable

### Step 2.1: Stop Worker Replicas (< 2 minutes)
```bash
# Scale all workers to 0 replicas (stops processing)
az containerapp update \
  --name sync-worker-$SUFFIX \
  --resource-group $RG \
  --min-replicas 0 \
  --max-replicas 0

az containerapp update \
  --name merge-worker-$SUFFIX \
  --resource-group $RG \
  --min-replicas 0 \
  --max-replicas 0

az containerapp update \
  --name training-worker-$SUFFIX \
  --resource-group $RG \
  --min-replicas 0 \
  --max-replicas 0

echo "✓ All workers stopped"
```

---

### Step 2.2: Purge Message Queues (< 1 minute)
```bash
# Delete all messages from queues (prevents backlog)
redis-cli -h $REDIS_HOST DEL github-sync-queue
redis-cli -h $REDIS_HOST DEL merge-queue
redis-cli -h $REDIS_HOST DEL training-queue

# Verify queues empty
redis-cli -h $REDIS_HOST LLEN github-sync-queue  # Should return 0

echo "✓ Queues purged"
```

**Data Loss**: In-flight messages lost (acceptable during rollback)

---

### Step 2.3: Disable Gateway Ingress (Optional)
```bash
# If gateway is causing issues, disable external traffic
az containerapp ingress update \
  --name gateway-$SUFFIX \
  --resource-group $RG \
  --type internal  # Only accessible within VNet

echo "✓ Gateway ingress disabled (internal only)"
```

---

### Step 2.4: Restart Function App (Force Refresh)
```bash
# Restart to ensure Key Vault secrets refreshed
az functionapp restart \
  --name $FUNCTION_APP_NAME \
  --resource-group $RG

echo "✓ Function App restarted"
```

**Wait 3-5 minutes for Function App warmup**

---

### Step 2.5: Verify Durable Functions Active
```bash
# Test orchestration endpoint directly
curl -X POST "$FUNCTION_APP_URL/api/orchestrator_start" \
  -H "Content-Type: application/json" \
  -d '{"username": "yungryce", "force_refresh": false}'

# Should return Durable Functions response:
# { "id": "...", "statusQueryGetUri": "..." }
```

**If successful** → Level 2 rollback complete  
**If still failing** → Proceed to Level 3

---

## Level 3: Full Revert (Nuclear Option)

### Step 3.1: Delete Queue Infrastructure (< 5 minutes)
```bash
# Delete Redis cache
az redis delete \
  --name redis-$SUFFIX \
  --resource-group $RG \
  --yes

# Delete all container apps
az containerapp delete --name gateway-$SUFFIX --resource-group $RG --yes
az containerapp delete --name sync-worker-$SUFFIX --resource-group $RG --yes
az containerapp delete --name merge-worker-$SUFFIX --resource-group $RG --yes

echo "✓ Queue infrastructure deleted"
```

---

### Step 3.2: Remove Feature Flags from Key Vault
```bash
# Delete queue-related secrets
az keyvault secret delete --vault-name $KV_NAME --name "QUEUE-TRAFFIC-PCT"
az keyvault secret delete --vault-name $KV_NAME --name "ENABLE-QUEUE-MODE"
az keyvault secret delete --vault-name $KV_NAME --name "REDIS-URL"

echo "✓ Feature flags removed"
```

---

### Step 3.3: Revert Bicep to Pre-Migration State
```bash
# Checkout Bicep from before migration
cd ~/DEV/portfolio/infra
git checkout $(git log --all --grep="Pre-queue migration" --format="%H" -1) -- main.bicep

# Redeploy infrastructure
az deployment group create \
  --resource-group $RG \
  --template-file main.bicep \
  --parameters suffix=$SUFFIX

echo "✓ Infrastructure reverted to pre-migration state"
```

---

### Step 3.4: Verify Function App Health
```bash
# Check Function App status
az functionapp show \
  --name $FUNCTION_APP_NAME \
  --resource-group $RG \
  --query "{Name:name, State:state, HealthCheckStatus:healthCheckStatus}" \
  -o table

# Run health check
curl "$FUNCTION_APP_URL/api/health"

# Expected: {"status": "healthy", "cache": "connected"}
```

---

## Post-Rollback Actions

### Immediate (Within 1 hour)
- [ ] **Notify Stakeholders**: Post incident report to Slack/Teams
- [ ] **Update Status Page**: "Queue-based architecture temporarily disabled"
- [ ] **Preserve Logs**: Export Application Insights errors for root cause analysis
- [ ] **Freeze Deployments**: Halt all CI/CD pipelines until stable

---

### Short-Term (Within 24 hours)
- [ ] **Root Cause Analysis**: Review diagnostics, identify failure point
- [ ] **Fix & Test**: Reproduce issue in staging, validate fix
- [ ] **Update Rollback Playbook**: Document any lessons learned
- [ ] **Stakeholder Review**: Decide on re-enabling timeline

---

### Long-Term (Within 1 week)
- [ ] **Post-Mortem**: Write incident report (template below)
- [ ] **Improve Monitoring**: Add alerts that would have caught issue earlier
- [ ] **Load Testing**: Validate fix under simulated production load
- [ ] **Gradual Re-Enable**: Start at 1% traffic, monitor for 48h

---

## Incident Report Template

```markdown
# Incident Report: Queue Architecture Rollback

**Date**: YYYY-MM-DD  
**Duration**: X hours (detection → resolution)  
**Impact**: X% of users affected, Y requests failed  
**Root Cause**: [Brief summary]

## Timeline
- HH:MM - Issue detected (alert triggered)
- HH:MM - Rollback decision made
- HH:MM - Level 1 rollback executed
- HH:MM - Service restored to normal

## Root Cause
[Detailed analysis with logs, metrics, code references]

## Why Detection Was Delayed
[If applicable: why alerts didn't catch earlier]

## Resolution
[What fixed the issue]

## Lessons Learned
1. **What went well**: [e.g., rollback was fast, data preserved]
2. **What went poorly**: [e.g., monitoring didn't alert early]
3. **Action items**:
   - [ ] Add alert for queue depth > 500
   - [ ] Pre-warm workers to avoid cold start latency
   - [ ] Document failure mode in troubleshooting guide

## Follow-Up
- [ ] Review load test scenarios to include this failure
- [ ] Update CI/CD to catch issue in staging
- [ ] Schedule re-enablement date
```

---

## Rollback Decision Matrix

| Symptom | Rollback Level | ETA | Action |
|---------|----------------|-----|--------|
| Error rate 2-5% | Level 1 | 2 min | Disable traffic to queues |
| Error rate > 5% | Level 2 | 10 min | Stop workers, purge queues |
| Queue depth > 1000 | Level 2 | 10 min | Purge queues, scale workers to 0 |
| Cache corruption | Level 2 | 10 min | Stop workers, investigate cache |
| Gateway unresponsive | Level 2 | 10 min | Disable gateway ingress |
| Multiple systems failing | Level 3 | 30 min | Full infrastructure revert |
| Data loss detected | Level 3 | 30 min | Revert to last known good state |

---

## Testing Rollback Procedures

**Before Migration**: Test rollback in staging

```bash
# 1. Deploy queue infrastructure in staging
az deployment group create --resource-group $STAGING_RG --template-file infra/main.bicep

# 2. Enable queue routing (simulate production)
az keyvault secret set --vault-name $STAGING_KV --name "QUEUE-TRAFFIC-PCT" --value "100"

# 3. Generate test load (via Locust)
locust -f tests/load_test.py --host=$STAGING_URL --users=50 --spawn-rate=10 --run-time=5m

# 4. Execute Level 1 rollback (following playbook)
az keyvault secret set --vault-name $STAGING_KV --name "QUEUE-TRAFFIC-PCT" --value "0"

# 5. Verify: All traffic routes to Durable Functions
# Expected: No errors, latency within normal bounds
```

**Validation**: Rollback completes in < 5 minutes, error rate < 0.5%

---

## Emergency Contacts

| Role | Name | Contact | Availability |
|------|------|---------|--------------|
| Backend Lead | [Your Name] | Slack: @you, Phone: +1-XXX | 24/7 during migration |
| DevOps Engineer | [Name] | Slack: @devops | Mon-Fri 9am-5pm |
| On-Call Rotation | PagerDuty | [Link] | 24/7 |

---

## Quick Reference Commands

```bash
# Export environment variables (run once per session)
export RG="portfolio-prod"
export SUFFIX="prod"
export KV_NAME="kv-portfolio-$SUFFIX"
export APP_INSIGHTS_NAME="appi-portfolio-$SUFFIX"
export FUNCTION_APP_NAME="fa-portfolio-$SUFFIX"
export REDIS_HOST="redis-$SUFFIX.redis.cache.windows.net"
export GATEWAY_URL="https://gateway-$SUFFIX.azurecontainerapps.io"

# Disable queue routing (Level 1)
az keyvault secret set --vault-name $KV_NAME --name "QUEUE-TRAFFIC-PCT" --value "0"

# Check error rate (last 5 minutes)
az monitor app-insights query --app $APP_INSIGHTS_NAME \
  --analytics-query "requests | where timestamp > ago(5m) | summarize errors=countif(resultCode >= 400), total=count() | extend pct = errors * 100.0 / total" \
  --output table

# Purge queue
redis-cli -h $REDIS_HOST DEL github-sync-queue

# Restart Function App
az functionapp restart --name $FUNCTION_APP_NAME --resource-group $RG
```

---

**Status**: Active Playbook  
**Review Frequency**: Weekly during migration, monthly post-cutover  
**Last Tested**: [Date]
