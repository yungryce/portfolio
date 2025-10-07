# GitHub Projects Board Structure

**Project Name**: CloudFolio Migration: Canary → Early Adoption  
**Board Type**: Kanban  
**View Mode**: Board + Table  

---

## Board Columns

### 1. 📋 Backlog
**Purpose**: All identified tasks not yet prioritized for current sprint

**Automation Rules**:
- New issues auto-add here
- No status filter (acts as intake)

**Example Items**:
- Research tasks
- Future phase work
- Low-priority improvements

---

### 2. 📝 To Do
**Purpose**: Prioritized tasks ready to be worked on in current phase

**Automation Rules**:
- Issues with `status: ready` label
- Manually moved from Backlog during planning
- Assigned to specific phase milestone

**Entry Criteria**:
- Task has clear acceptance criteria
- Dependencies documented
- Assignee identified (can be TBD)

---

### 3. 🚧 In Progress
**Purpose**: Active work items currently being implemented

**Automation Rules**:
- Issues with `status: in-progress` label
- PR linked to issue also shows here
- Max 3 items per person (WIP limit)

**Exit Criteria**:
- Code committed + PR opened
- Local testing passed
- Moves to "In Review"

---

### 4. 👀 In Review
**Purpose**: Work awaiting code review, testing, or approval

**Automation Rules**:
- PR opened → auto-moves here
- PR approved → moves to "Done"
- PR changes requested → moves back to "In Progress"

**Review Checklist**:
- [ ] Code follows project conventions
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No new lint/compile errors

---

### 5. ✅ Done
**Purpose**: Completed work merged to main branch

**Automation Rules**:
- PR merged → auto-moves here
- Issue closed → auto-archives after 7 days

**Success Criteria**:
- Deployed to staging (or production if appropriate)
- Acceptance criteria validated
- Monitoring/alerts configured (if applicable)

---

## Labels Schema

### Priority Labels
- 🔴 `priority: critical` - Blocking other work, fix immediately
- 🟠 `priority: high` - Important for current phase success
- 🟡 `priority: medium` - Should be done but not blocking
- 🟢 `priority: low` - Nice to have, backlog candidate

### Phase Labels (Milestones)
- `phase-1: cache-layer` - Cache standardization work
- `phase-2: model-training` - Model training decoupling
- `phase-3: github-sync` - GitHub API optimization
- `phase-4: multi-tenant` - Multi-tenant preparation
- `phase-5: observability` - Monitoring & rollback
- `phase-6: production-ready` - Final hardening

### Type Labels
- `type: feature` - New functionality
- `type: refactor` - Code improvement, no behavior change
- `type: bug` - Something broken
- `type: docs` - Documentation updates
- `type: infra` - Infrastructure/deployment changes
- `type: testing` - Test coverage improvements

### Component Labels
- `component: api` - Backend Azure Functions
- `component: frontend` - Angular application
- `component: infra` - Bicep/infrastructure
- `component: cache` - Cache manager changes
- `component: ai` - AI/ML model work
- `component: github` - GitHub API integration

### Status Labels (Track Stage)
- `status: blocked` - Cannot proceed due to dependency
- `status: ready` - Ready to start work
- `status: in-progress` - Actively being worked
- `status: needs-review` - Awaiting feedback
- `status: needs-testing` - Requires manual testing

---

## Milestones

### Week 1: Cache Standardization
**Due Date**: Week 1 Friday  
**Description**: Establish cache as single source of truth with multi-tenant isolation  
**Success Criteria**:
- All cache operations log tenant context
- Cache hit rate tracked per username
- `CACHE-CONTRACT.md` published

**Key Issues**:
1. Audit existing cache keys
2. Add tenant metadata to blobs
3. Implement quota tracking methods
4. Create cache service README
5. Add Application Insights monitoring

---

### Week 2: Model Training Queue
**Due Date**: Week 2 Friday  
**Description**: Decouple model training from orchestration via Azure Storage Queue  
**Success Criteria**:
- Queue messages processed successfully
- Feature flag `ENABLE_ASYNC_MODEL_TRAINING` implemented
- Inline training still works as fallback

**Key Issues**:
1. Create Azure Storage Queue
2. Update orchestrator to queue training jobs
3. Add feature flag infrastructure
4. Test queue message format
5. Document rollback procedure

---

### Week 3: Training Service Deployment
**Due Date**: Week 3 Friday  
**Description**: Deploy isolated model training service on Azure Container Instances  
**Success Criteria**:
- 3 successful training runs without errors
- ACI auto-deprovisions after training
- Cost per training run tracked

**Key Issues**:
1. Create `api/services/model-training/` structure
2. Write Dockerfile for training service
3. Create ACI Bicep module
4. Deploy to staging environment
5. Enable async training feature flag

---

### Week 4: GitHub Sync Optimization
**Due Date**: Week 4 Friday  
**Description**: Reduce GitHub API calls via GraphQL batching  
**Success Criteria**:
- API calls reduced by 50%
- Zero 429 rate limit errors
- Orchestration 20% faster for large bundles

**Key Issues**:
1. Profile current API call patterns
2. Implement GraphQL batch fetch
3. Add rate limit backoff logic
4. Monitor API quota usage
5. Performance comparison report

---

### Week 5: Multi-Tenant Preparation
**Due Date**: Week 5 Friday  
**Description**: Prepare all services for multi-user isolation  
**Success Criteria**:
- All logs include `username` field
- Admin dashboard shows per-user metrics
- No hardcoded usernames in production paths

**Key Issues**:
1. Audit and remove hardcoded usernames
2. Add tenant context to structured logs
3. Implement usage tracking per user
4. Add soft quota checks
5. Create admin Azure Workbook

---

### Week 6: Observability & Rollback
**Due Date**: Week 6 Friday  
**Description**: Establish monitoring and rollback procedures  
**Success Criteria**:
- All alerts fire correctly in staging
- Runbook covers common issues
- Each feature flag has documented rollback

**Key Issues**:
1. Create Application Insights dashboards
2. Configure alert rules
3. Write runbook for operations
4. Test rollback procedures
5. Create Postman health check collection

---

## Issue Templates

### Feature Issue Template
```markdown
## Description
[Clear description of the feature]

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Documentation updated

## Implementation Notes
[Technical details, API changes, etc.]

## Dependencies
- Blocked by: #[issue-number]
- Related to: #[issue-number]

## Testing Plan
[How to verify this works]

## Rollback Plan
[How to revert if something breaks]
```

### Bug Issue Template
```markdown
## Bug Description
[What's broken]

## Steps to Reproduce
1. Step 1
2. Step 2
3. See error

## Expected Behavior
[What should happen]

## Actual Behavior
[What actually happens]

## Environment
- Function App: [name]
- Username: [affected user]
- Timestamp: [when it occurred]

## Logs/Screenshots
[Paste relevant logs or screenshots]

## Proposed Fix
[If known]
```

### Documentation Issue Template
```markdown
## Documentation Needed
[What needs to be documented]

## Target Audience
- [ ] Developers
- [ ] DevOps
- [ ] End Users

## Key Topics to Cover
- Topic 1
- Topic 2

## Related Code/Services
[Links to relevant code]

## Success Criteria
- [ ] Documentation published
- [ ] Reviewed by team
- [ ] Examples tested
```

---

## Automation Rules

### Auto-Move to "In Progress"
**Trigger**: Issue assigned + label `status: ready` removed  
**Action**: Move to "In Progress" column

### Auto-Move to "In Review"
**Trigger**: PR opened and linked to issue  
**Action**: Move issue to "In Review" column

### Auto-Move to "Done"
**Trigger**: PR merged to main  
**Action**: Move issue to "Done", add comment with deployment info

### Stale Issue Warning
**Trigger**: Issue in "In Progress" with no updates for 7 days  
**Action**: Add comment requesting status update, label `status: needs-update`

### Blocked Issue Highlight
**Trigger**: Issue labeled `status: blocked`  
**Action**: Add red border, move to top of column, mention in weekly standup

---

## Weekly Workflow

### Monday: Sprint Planning
1. Review "Backlog" column
2. Move prioritized items to "To Do"
3. Assign issues to team members
4. Update milestone progress

### Daily: Standup
1. Review "In Progress" column
2. Identify blockers (label `status: blocked`)
3. Check for stale issues (no updates >3 days)
4. Move completed items to "Done"

### Friday: Sprint Review
1. Demo completed items from "Done"
2. Update milestone completion percentage
3. Document lessons learned
4. Plan next week's priorities

---

## Reporting & Metrics

### Velocity Chart
**Track**: Issues completed per week per phase  
**Goal**: Maintain consistent velocity, identify bottlenecks

### Burndown Chart
**Track**: Remaining issues per milestone  
**Goal**: Stay on track for phase deadlines

### Cycle Time
**Track**: Average time from "In Progress" → "Done"  
**Goal**: Reduce cycle time below 3 days per issue

### Blocked Time
**Track**: Total days issues spent in `status: blocked`  
**Goal**: Minimize blocked time, resolve dependencies quickly

---

## References

- Main Migration Plan: [MIGRATION-PLAN.md](./MIGRATION-PLAN.md)
- AI Agent Guides: [../copilot-instructions.md](../copilot-instructions.md)
- Architecture Docs: [../../ARCHITECTURE.md](../../ARCHITECTURE.md)

---

**Board Maintainer**: Migration Team Lead  
**Last Updated**: October 7, 2025  
**Board URL**: https://github.com/yungryce/portfolio/projects/[project-number]
