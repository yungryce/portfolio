# CloudFolio Migration Project Documentation

**Project**: CloudFolio Canary → Early Adoption Migration  
**Status**: Planning Phase  
**Start Date**: October 7, 2025  
**Timeline**: 6 weeks  

---

## 📚 Documentation Index

### Core Planning Documents
1. **[MIGRATION-PLAN.md](./MIGRATION-PLAN.md)** - Master migration strategy
   - 6-phase timeline (Cache → Model Training → GitHub Sync → Multi-Tenant → Observability)
   - Success metrics, risk management, rollback procedures
   - **Start here** for overall context

2. **[GITHUB-PROJECT-STRUCTURE.md](./GITHUB-PROJECT-STRUCTURE.md)** - Kanban board setup
   - Column definitions (Backlog → To Do → In Progress → In Review → Done)
   - Labels schema (priority, phase, type, component)
   - Issue templates and automation rules

3. **[CACHE-CONTRACT.md](./CACHE-CONTRACT.md)** - Cache API specification
   - All cache key types (bundle, repo, model)
   - TTL policies, fingerprint logic
   - Monitoring queries and quota tracking

4. **[MULTI-TENANT-DESIGN.md](./MULTI-TENANT-DESIGN.md)** - Tenant isolation patterns
   - Username-based routing and quota enforcement
   - Log context, security considerations
   - Migration path from single-user to multi-tenant

5. **[AI-AGENT-GUIDE.md](./AI-AGENT-GUIDE.md)** - Development guide for AI assistants
   - Coding patterns, common workflows
   - Testing checklist, debugging steps
   - Quick reference commands

---

## 🚀 Quick Start

### For Human Developers
1. Read [MIGRATION-PLAN.md](./MIGRATION-PLAN.md) for overall strategy
2. Review [GITHUB-PROJECT-STRUCTURE.md](./GITHUB-PROJECT-STRUCTURE.md) to understand board workflow
3. Check [AI-AGENT-GUIDE.md](./AI-AGENT-GUIDE.md) for coding patterns
4. Pick an issue from "To Do" column in GitHub Projects board

### For AI Coding Agents
1. Load context from [AI-AGENT-GUIDE.md](./AI-AGENT-GUIDE.md)
2. Read phase-specific docs ([CACHE-CONTRACT.md](./CACHE-CONTRACT.md), [MULTI-TENANT-DESIGN.md](./MULTI-TENANT-DESIGN.md))
3. Follow patterns in [../copilot-instructions.md](../copilot-instructions.md)
4. Execute task following testing checklist

---

## 📋 Migration Phases Overview

| Phase | Week | Focus | Key Deliverable |
|-------|------|-------|----------------|
| **Phase 1** | 1 | Cache Standardization | `CACHE-CONTRACT.md` + monitoring dashboard |
| **Phase 2** | 2-3 | Model Training Decoupling | ACI training service + feature flag |
| **Phase 3** | 4 | GitHub Sync Optimization | GraphQL batch fetching |
| **Phase 4** | 5 | Multi-Tenant Preparation | Usage tracking + admin dashboard |
| **Phase 5** | 6 | Observability & Rollback | Runbook + alert rules |

**Current Phase**: Phase 0 (Planning & Documentation)

---

## 🎯 Success Criteria

### Technical Metrics
- **Orchestration Duration**: 45s → 30s (p95)
- **Cache Hit Rate**: 65% → 85%
- **GitHub API Calls**: 40 → 20 per bundle
- **Cost per 1000 Requests**: $0.50 → $0.35

### Migration Readiness
- ✅ All docs published
- ✅ GitHub Project board created
- ⏳ Phase 1 tasks defined (in progress)
- ⏳ Staging environment prepared
- ⏳ Team onboarded on workflow

---

## 🔗 Related Documentation

### Project Root
- [../../ARCHITECTURE.md](../../ARCHITECTURE.md) - System architecture overview
- [../../README.md](../../README.md) - Project introduction
- [../../SKILLS-INDEX.md](../../SKILLS-INDEX.md) - Technical competencies demonstrated

### Codebase-Specific
- [../../api/.github/copilot-instructions.md](../../api/.github/copilot-instructions.md) - Backend patterns
- [../../src/.github/copilot-instructions.md](../../src/.github/copilot-instructions.md) - Frontend patterns
- [../copilot-instructions.md](../copilot-instructions.md) - Global coding conventions

### Infrastructure
- [../../infra/main.bicep](../../infra/main.bicep) - Azure resource definitions
- [../../azure-pipelines-artifact.yml](../../azure-pipelines-artifact.yml) - CI/CD for app code
- [../../azure-pipelines-infra.yml](../../azure-pipelines-infra.yml) - CI/CD for infrastructure

---

## 📊 Progress Tracking

### GitHub Projects Board
**URL**: https://github.com/yungryce/portfolio/projects/[project-number]  
**Views**:
- **Board View**: Kanban columns for visual progress
- **Table View**: List with filters (phase, priority, assignee)
- **Roadmap View**: Timeline visualization

### Weekly Cadence
- **Monday**: Sprint planning (move issues to "To Do")
- **Daily**: Standup via board updates (async)
- **Friday**: Sprint review (demo "Done" items)

### Reporting
- **Velocity Chart**: Issues closed per week
- **Burndown Chart**: Remaining issues per milestone
- **Cycle Time**: Average "In Progress" → "Done" duration

---

## 🛠️ Development Setup

### Prerequisites
- **Backend**: Python 3.11+, Azure Functions Core Tools 4.x, Azure CLI
- **Frontend**: Node.js 20.x, Angular CLI 17+
- **Infrastructure**: Bicep CLI, Azure subscription with Owner access

### Local Environment
```bash
# Backend
cd api/
pip install -r requirements.txt
cp local.settings.json.template local.settings.json  # Edit with tokens
func start

# Frontend
npm install
npm run start

# Infrastructure (dry-run)
cd infra/
az bicep build --file main.bicep
```

### Environment Variables
**Required for local development**:
- `GITHUB_TOKEN`: Personal access token for GitHub API
- `GROQ_API_KEY`: API key for Groq LLM
- `AzureWebJobsStorage`: Connection string for local Azure Storage Emulator

**Optional**:
- `DEFAULT_USERNAME`: Default user (defaults to `yungryce`)
- `ENABLE_ASYNC_MODEL_TRAINING`: Feature flag (defaults to `false`)

---

## 🐛 Troubleshooting

### Issue: Cache operations fail locally
**Cause**: Missing `AzureWebJobsStorage` environment variable  
**Solution**: Set to Azure Storage connection string or use local emulator:
```bash
export AzureWebJobsStorage="UseDevelopmentStorage=true"
```

### Issue: Orchestration stuck "Running"
**Cause**: Activity function error not surfaced  
**Solution**: Check logs in `api/api_function_app.log` or Application Insights:
```bash
tail -f api/api_function_app.log
```

### Issue: Frontend can't reach backend
**Cause**: CORS not configured in `local.settings.json`  
**Solution**: Add CORS origins:
```json
{
  "Host": {
    "CORS": "*"
  }
}
```

---

## 📝 Contributing Workflow

### 1. Pick a Task
- Go to GitHub Projects board
- Filter by your assigned issues or `status: ready`
- Move issue to "In Progress" column

### 2. Create Feature Branch
```bash
git checkout -b feature/phase1-cache-audit
```

### 3. Implement Changes
- Follow patterns in [AI-AGENT-GUIDE.md](./AI-AGENT-GUIDE.md)
- Add tests if applicable
- Update documentation

### 4. Local Testing
```bash
# Backend
cd api/
pytest
func start  # Manual smoke test

# Frontend
npm test
npm run start  # Manual smoke test
```

### 5. Create Pull Request
- Link issue in PR description: `Closes #123`
- Request review from team
- Address feedback and re-request review

### 6. Merge & Deploy
- After approval, merge to `main`
- Azure Pipelines auto-deploys to staging
- Validate in staging before production promotion

---

## 📞 Contact & Support

### Team Communication
- **Slack Channel**: `#cloudfolio-migration` (if applicable)
- **GitHub Discussions**: Use for questions about migration plan
- **Email**: [team email] for urgent issues

### Escalation Path
1. **Blocked on task**: Add `status: blocked` label, mention in daily standup
2. **Technical decision needed**: Create discussion issue with `needs: decision` label
3. **Production incident**: Follow runbook in [MIGRATION-PLAN.md](./MIGRATION-PLAN.md)

---

## 🎓 Training Resources

### Azure Functions
- [Azure Functions Python Guide](https://docs.microsoft.com/en-us/azure/azure-functions/functions-reference-python)
- [Durable Functions Overview](https://docs.microsoft.com/en-us/azure/azure-functions/durable/durable-functions-overview)

### Angular
- [Angular Official Guide](https://angular.io/guide/architecture)
- [RxJS Operator Reference](https://rxjs.dev/api)

### Azure DevOps
- [Bicep Language Reference](https://docs.microsoft.com/en-us/azure/azure-resource-manager/bicep/)
- [Application Insights KQL](https://docs.microsoft.com/en-us/azure/data-explorer/kusto/query/)

---

## 📅 Next Steps

### Immediate (This Week)
- [ ] Create GitHub Projects board using [GITHUB-PROJECT-STRUCTURE.md](./GITHUB-PROJECT-STRUCTURE.md)
- [ ] Break down Phase 1 into granular issues (see sample issues below)
- [ ] Set up staging environment (clone production config)
- [ ] Schedule kickoff meeting with team

### Short-Term (Week 1)
- [ ] Begin Phase 1: Cache Standardization
- [ ] Set up Application Insights dashboard
- [ ] Establish monitoring baselines
- [ ] Document local dev environment setup

### Long-Term (Weeks 2-6)
- [ ] Execute remaining phases per timeline
- [ ] Weekly progress reviews
- [ ] Continuous documentation updates
- [ ] Production cutover planning

---

## 📜 Document History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2025-10-07 | Initial migration plan created | Migration Team |
| 1.1 | TBD | After Phase 1 completion | TBD |

---

## 📄 License & Confidentiality

**License**: Same as main project (see [../../LICENSE](../../LICENSE))  
**Confidentiality**: Internal project documentation, do not distribute outside organization

---

**Maintained by**: CloudFolio Migration Team  
**Last Updated**: October 7, 2025  
**Status**: Living document (updated after each phase)
