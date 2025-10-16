# GitHub Projects Board Structure

**Project Name**: CloudFolio Migration: Canary → Early Adoption  
**Board Type**: Kanban (Continuous Flow)  
**View Mode**: Board + Table  

---

## 🎯 Kanban Philosophy

This board follows **pull-based workflow** principles:
- ✅ **No time-boxed sprints** - Tasks move based on capacity, not calendar
- ✅ **WIP limits** - Constrain work in progress to maintain flow
- ✅ **Continuous delivery** - Deploy to staging whenever a task completes
- ✅ **Pull from backlog** - Developers pull next priority item when ready
- ✅ **Phase labels** - Organize work without rigid milestones

---

## Board Columns

### 1. 📋 Backlog
**Purpose**: All identified tasks not yet ready to work

**Acceptance Criteria for Entry**:
- Task has clear description
- Dependencies identified (even if not resolved)
- Rough effort estimate (S/M/L)

**Automation Rules**:
- New issues auto-add here
- Issues with `status: needs-refinement` stay here

**Example Items**:
- Research spikes
- Future phase work
- Ideas without clear acceptance criteria

**Column Limit**: None (this is the intake)

---

### 2. 📝 Ready
**Purpose**: Prioritized, actionable tasks ready to be pulled by any developer

**Acceptance Criteria**:
- [ ] Clear acceptance criteria defined
- [ ] All blocking dependencies resolved
- [ ] Implementation approach agreed upon
- [ ] Can be completed by one person in 1-3 days

**Automation Rules**:
- Must have `status: ready` label
- Must be assigned to a phase (`phase-1`, `phase-2`, etc.)
- Sorted by priority (critical → high → medium)

**Pull Trigger**: Developer finishes current work, pulls top item

**Column Limit**: 15 items (ensures healthy backlog grooming)

---

### 3. 🚧 In Progress
**Purpose**: Active work currently being implemented

**WIP Limit**: **3 items per person** (hard limit)  
**Team WIP Limit**: **6 total** (for 2-3 person team)

**Automation Rules**:
- Assign issue to yourself when moving here
- Add `status: in-progress` label
- Link to feature branch or PR (draft OK)

**Exit Criteria**:
- Code committed to feature branch
- Local tests pass
- PR opened (can be draft)

**Blocked Items**: Add `status: blocked` label, move back to Ready, document blocker

**Daily Check**: If item >3 days old, team discusses in standup

---

### 4. 👀 In Review
**Purpose**: Work awaiting code review, testing, or approval

**WIP Limit**: **5 items** (prevents review bottleneck)

**Automation Rules**:
- PR opened → auto-moves here
- PR marked as "ready for review" → notifies team
- PR approved + CI passes → moves to Done

**Review SLA**: 24 hours for first review

**Review Checklist**:
- [ ] Code follows [AI-AGENT-GUIDE.md](./AI-AGENT-GUIDE.md) patterns
- [ ] Tests added/updated (if applicable)
- [ ] Documentation updated
- [ ] Tenant context in logs (Phase 4+)
- [ ] Feature flag used for risky changes
- [ ] No new lint/security warnings

**Fast-Track**: Small fixes (<20 lines) can merge with single approval

---

### 5. ✅ Done
**Purpose**: Completed work merged to main and deployed to staging

**Definition of Done**:
- [ ] PR merged to `main`
- [ ] Deployed to staging environment
- [ ] Acceptance criteria validated
- [ ] Monitoring/alerts configured (if applicable)
- [ ] Documentation updated
- [ ] Original issue closed with deployment notes

**Automation Rules**:
- PR merged → auto-moves here
- Auto-archive after 7 days
- Comment with deployment timestamp

**Column Limit**: 20 items (auto-archive older)

---

## 🏷️ Labels Schema

### Priority Labels (Sort Order in Ready Column)
```
🔴 priority: critical   - Blocking other work, production issue, security flaw
🟠 priority: high       - Needed for phase completion, major feature
🟡 priority: medium     - Important but not blocking
🟢 priority: low        - Nice to have, tech debt, optimization
```

**Priority Rules**:
- Only 1-2 `critical` items allowed at a time
- Reassess priority weekly in backlog grooming

---

### Phase Labels (Organize by Architecture Layer)
```
phase-1: cache-layer        - Cache standardization & contract
phase-2: model-training     - Training service decoupling
phase-3: github-sync        - GitHub API optimization
phase-4: multi-tenant       - Multi-user preparation
phase-5: observability      - Monitoring & alerting
phase-6: production-ready   - Final hardening & launch prep
```

**Phase Progression**: Later phases can start before earlier ones complete (non-blocking)

---

### Type Labels (Work Category)
```
type: feature       - New functionality
type: refactor      - Code improvement, no behavior change
type: bug          - Something broken
type: docs         - Documentation updates
type: infra        - Infrastructure/deployment changes
type: testing      - Test coverage improvements
type: spike        - Research/investigation (time-boxed)
```

---

### Component Labels (Codebase Area)
```
component: api          - Backend Azure Functions (function_app.py)
component: frontend     - Angular application
component: infra        - Bicep/infrastructure
component: cache        - Cache manager changes
component: ai           - AI/ML model work
component: github       - GitHub API integration
component: ci-cd        - Pipeline/deployment
```

---

### Status Labels (Track Blockers)
```
status: blocked         - Cannot proceed, reason in comment
status: ready          - Ready to pull into In Progress
status: in-progress    - Actively being worked
status: needs-review   - PR open, awaiting review
status: needs-testing  - Requires manual/staging validation
status: needs-refinement - Backlog item needs more detail
```

---

## 📊 Kanban Metrics (Track Flow)

### Cycle Time
**Definition**: Time from "In Progress" → "Done"  
**Target**: Average ≤ 3 days per issue  
**Chart**: Cumulative Flow Diagram

**Action if >3 days**:
- Break issue into smaller tasks
- Identify bottlenecks (review delays? testing?)

---

### Throughput
**Definition**: Issues completed per week  
**Baseline**: Week 1-2 establishes baseline  
**Goal**: Maintain ±20% of baseline (predictable flow)

**Chart**: Weekly completed items bar chart

---

### WIP (Work in Progress)
**Definition**: Items in "In Progress" + "In Review"  
**Limit**: 9 total (6 in progress + 3 in review per person)  
**Alert**: If WIP limit exceeded, stop pulling new work

**Action if limit hit**:
- Focus on completing existing work
- Swarm on oldest "In Review" item

---

### Lead Time
**Definition**: Time from "Backlog" → "Done"  
**Target**: 90% of items ≤ 7 days  
**Chart**: Histogram of lead times

---

### Blocked Time
**Definition**: Days spent with `status: blocked` label  
**Target**: <5% of total cycle time  
**Alert**: Issue blocked >2 days → escalate

---

## 🔄 Continuous Workflows

### Daily (Async in Slack/Comments)
```
Morning (Each Developer):
1. Check "In Progress" - am I blocked?
2. Move completed items to "In Review"
3. If capacity available, pull from "Ready"
4. Update blockers on GitHub issues

Afternoon (Code Reviews):
1. Review oldest PR in "In Review" first
2. Approve or request changes within 2 hours
3. Merge approved PRs immediately
```

---

### Weekly: Backlog Grooming (30 min)
```
Tuesday 3pm (Whole Team):
1. Review "Backlog" - move refined items to "Ready"
2. Re-prioritize "Ready" column (drag to reorder)
3. Identify upcoming blockers/dependencies
4. Close stale issues (>30 days no activity)
5. Add new issues from support/monitoring

Output: Top 10 items in "Ready" are clear & prioritized
```

---

### Bi-Weekly: Metrics Review (15 min)
```
Every Other Friday:
1. Review cycle time trend
2. Check WIP limits compliance
3. Identify bottlenecks (Where do items get stuck?)
4. Adjust processes (e.g., add reviewers, break tasks smaller)

Dashboard: GitHub Insights → Velocity chart
```

---

## 🚀 Pull-Based Work Assignment

### How to Pull Work (Developer Guide)

#### Step 1: Check Capacity
```
Am I at my WIP limit? (3 items in "In Progress")
  ├─ YES → Finish current work before pulling new
  └─ NO  → Proceed to Step 2
```

#### Step 2: Find Next Task
```
Sort "Ready" column by:
  1. Priority (🔴 critical first)
  2. Phase (earlier phases preferred)
  3. Age (older issues first)

Pick top item that matches:
  ✓ Your skills/component familiarity
  ✓ No hard blockers
  ✓ Estimated ≤ 3 days
```

#### Step 3: Start Work
```bash
# On GitHub
1. Assign issue to yourself
2. Move to "In Progress"
3. Add comment: "Starting work on this"

# Locally
git checkout main
git pull origin main
git checkout -b feature/issue-123-short-description
```

#### Step 4: Signal Progress
```
Every 24 hours:
- Comment with progress update
- Push code to feature branch (even if incomplete)
- If blocked, move back to "Ready" + add blocker comment
```

---

## 🎨 Issue Templates

### Feature Issue (Copy-Paste into New Issue)
```markdown
## 📝 Description
[Clear 1-2 sentence description]

## 🎯 Acceptance Criteria
- [ ] Criterion 1 (testable)
- [ ] Criterion 2 (testable)
- [ ] Documentation updated
- [ ] Tests added/updated

## 🔨 Implementation Notes
**Approach**: [High-level plan]
**Files to Change**: 
- `api/config/cache_manager.py` - [what changes]
- `api/function_app.py` - [what changes]

**Dependencies**: [Libraries, other issues, etc.]

## 🧪 Testing Plan
**Local Test**:
```bash
# Steps to verify locally
pytest tests/test_cache_manager.py -v
```

**Staging Test**:
1. Deploy to staging
2. Run [specific API call]
3. Verify [expected outcome]

## 📚 References
- [CACHE-CONTRACT.md](./CACHE-CONTRACT.md#relevant-section)
- [AI-AGENT-GUIDE.md](./AI-AGENT-GUIDE.md#relevant-pattern)

## 🔙 Rollback Plan
If this breaks production:
```bash
# Revert feature flag
az functionapp config appsettings set --name $FUNC_APP --settings ENABLE_FEATURE=false
```

---
**Labels**: `phase-X`, `component:Y`, `priority:medium`, `type:feature`, `status:needs-refinement`  
**Estimate**: [S/M/L - Small <1 day, Medium 1-3 days, Large >3 days]
```

---

### Bug Issue (Copy-Paste into New Issue)
```markdown
## 🐛 Bug Description
[What's broken - be specific]

## 📍 Steps to Reproduce
1. Go to [URL or API endpoint]
2. Call with [specific parameters]
3. Observe [incorrect behavior]

## ✅ Expected Behavior
[What should happen]

## ❌ Actual Behavior
[What actually happens]

## 🌍 Environment
- **Function App**: `fa-portfolio-xyz`
- **Username**: `testuser`
- **Timestamp**: `2025-10-07T14:32:00Z`
- **Request ID**: `abc123` (from Application Insights)

## 📋 Logs/Screenshots
```json
// Paste relevant logs from Application Insights
{
  "message": "Error in cache_manager.get()",
  "exception": "KeyError: 'repos_bundle_context_testuser'"
}
```

## 🔍 Root Cause Analysis (if known)
[Technical details of why this is happening]

## 🛠️ Proposed Fix
[If you have a solution in mind]

---
**Labels**: `type:bug`, `priority:high`, `component:cache`, `status:ready`
```

---

### Spike Issue (Research/Investigation)
```markdown
## 🔬 Research Question
[What are we trying to learn?]

## 🎯 Success Criteria (Time-Boxed to 4 hours)
- [ ] Document findings in this issue
- [ ] Recommend approach (yes/no/needs-more-info)
- [ ] Identify risks/unknowns

## 📚 Resources to Review
- Azure docs: [link]
- Similar projects: [link]
- Stack Overflow: [link]

## 🎤 Presentation Format
[Add comment with]:
1. Summary (2-3 sentences)
2. Pros/Cons table
3. Recommendation
4. Next steps

---
**Labels**: `type:spike`, `phase-X`, `priority:medium`  
**Time Limit**: 4 hours max
```

---

## 🔧 Automation Rules (GitHub Actions)

### Auto-Label PRs
```yaml
# .github/workflows/pr-labeler.yml
on: pull_request
jobs:
  label:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/labeler@v4
        with:
          repo-token: "${{ secrets.GITHUB_TOKEN }}"
          configuration-path: .github/pr-labeler.yml
```

### Auto-Move Issues on PR Events
```yaml
# .github/workflows/project-automation.yml
on:
  pull_request:
    types: [opened, closed, reopened]
jobs:
  move-card:
    runs-on: ubuntu-latest
    steps:
      - name: Move to In Review
        if: github.event.action == 'opened'
        uses: alex-page/github-project-automation-plus@v0.8.1
        with:
          project: CloudFolio Migration
          column: In Review
```

### Stale Issue Bot
```yaml
# .github/workflows/stale.yml
on:
  schedule:
    - cron: '0 0 * * *' # Daily
jobs:
  stale:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/stale@v8
        with:
          days-before-stale: 30
          days-before-close: 7
          stale-issue-label: 'stale'
          stale-issue-message: >
            This issue has had no activity for 30 days.
            Add a comment or this will close in 7 days.
```

---

## 📋 Board Health Checklist

### Daily Health Check
- [ ] No items blocked >2 days
- [ ] WIP limits respected (3 per person, 6 team total)
- [ ] All "In Review" items <24 hours old
- [ ] "Ready" column has 10+ items

### Weekly Health Check
- [ ] Average cycle time ≤ 3 days
- [ ] Throughput stable (±20% of baseline)
- [ ] No stale issues >30 days in "Backlog"
- [ ] All phases have 2+ items in "Ready"

---

## 🎯 Success Indicators

**Healthy Kanban Flow**:
- ✅ Developers rarely idle waiting for work
- ✅ PRs reviewed within 24 hours
- ✅ No large "traffic jams" in any column
- ✅ Predictable delivery (similar throughput each week)
- ✅ Low context switching (finish before starting new)

**Warning Signs**:
- ⚠️ "In Progress" growing (WIP limit ignored)
- ⚠️ "In Review" piling up (review bottleneck)
- ⚠️ Cycle time >5 days (tasks too large)
- ⚠️ Many `status: blocked` items (dependency issues)

---

## 📚 References

- **Kanban Guide**: [kanbanize.com/kanban-resources/getting-started/what-is-kanban](https://kanbanize.com/kanban-resources/getting-started/what-is-kanban)
- **Main Migration Plan**: [MIGRATION-PLAN.md](./MIGRATION-PLAN.md)
- **AI Agent Guides**: [AI-AGENT-GUIDE.md](./AI-AGENT-GUIDE.md)
- **GitHub Projects Docs**: [docs.github.com/en/issues/planning-and-tracking-with-projects](https://docs.github.com/en/issues/planning-and-tracking-with-projects)

---

**Board Type**: Kanban (Continuous Flow)  
**Last Updated**: October 7, 2025  
**Maintainer**: Migration Team Lead  
**Board URL**: https://github.com/yungryce/portfolio/projects/[project-number]
