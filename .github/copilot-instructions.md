# Copilot Instructions for Portfolio Project

Concise, codebase-specific guidance.

## Big Picture
- **Frontend**: Angular standalone application (17+) styled with Tailwind CSS. Entry point is `main.ts`, and routing is defined in `app/app.routes.ts`.
- **Backend**: Azure Functions (Python) serving GitHub data bundles and AI endpoints. Key entry file: `api/function_app.py`.
- **Integration**: The frontend communicates with the backend via REST API endpoints, with the base URL managed by `ConfigService.apiUrl`.

## Refactor Direction
- **Projects List**: `src/app/projects` consumes `RepoBundleService.getUserBundle(username)` to display repositories as cards. Deprecate `src/projects-old`.
- **Project Detail**: `src/app/projects/project` consumes `RepoBundleService.getUserSingleRepoBundle(username, repo)` to display single repository details. Deprecate `src/projects-old/project-about`.
- **AI Assistant**: `src/app/assistant` consumes `api/function-app.portfolio_query` for AI responses. Deprecate `src/portfolio-assistant`.

## Developer Workflows
- **Frontend**:
  - Start dev server: `npm run start` or `ng serve`.
  - Build production: `npm run build` or `ng build`.
- **Backend**:
  - Install dependencies: `cd api && pip install -r requirements.txt`.
  - Start Azure Functions locally: `func start`.
  - Logs: `api/api_function_app.log` for debugging.
- **Testing**:
  - Frontend: `ng test`.
  - Backend: `pytest` (ensure Python 3.11+ is installed).

## Theming (Dark/Light Mode)
- Global `<html>.dark` class toggles themes.
- Tokens in `src/styles.css`: `--bg`, `--fg`, `--primary`, etc.
- On init: Read `localStorage.theme` or `prefers-color-scheme`.
- Apply: Add/remove `dark` class on `<html>` and set `data-theme`.

## API Endpoints
- **Bundles**:
  - `GET /bundles/{username}` → `{ username, data: Repo[] }`.
  - `GET /bundles/{username}/{repo}` → `{ username, repo, data: Repo }`.
- **AI**:
  - `POST /ai` → `{ query, username? }` → AI assistant reply.
- **Health Check**:
  - `GET /api/health` → Returns environment and cache status.

## Project-Specific Patterns
- **Error Handling**:
  - Use `create_success_response` and `create_error_response` for consistent API responses.
  - For GitHub API errors, use `handle_github_error`.
- **Caching**:
  - Centralized in `config/cache_manager.py`.
  - Keys: `repos_bundle_context_{username}`, `repo_context_{username}_{repo}`.
- **Logging**:
  - Use structured logging with `portfolio.api` logger.

## UI/ViewModel Conventions
- **Projects List**:
  - Map API data to view model using `toCardVM`.
  - Display title, updated date, type, description, primary stack, and language percentages.
- **Project Detail**:
  - Render README as sanitized Markdown with a linked Table of Contents.
- **Accessibility**:
  - Use `aria-pressed` for theme toggles and `role="progressbar"` for language bars.

## Integration Points
- **Frontend**:
  - `RepoBundleService`: Fetches repository bundles.
  - `AIAssistantService`: Sends queries to the AI endpoint.
- **Backend**:
  - `GitHubRepoManager`: Fetches metadata, file content, and repository trees.
  - `RepoScoringService`: Scores repositories for AI queries.

## Examples
- **Normalize Language Percentages**:
  ```typescript
  const total = Object.values(langs).reduce((a, b) => a + Number(b), 0) || 1;
  Object.entries(langs)
    .map(([k, v]) => ({ k, pct: Math.round((Number(v) / total) * 100) }))
    .sort((a, b) => b.pct - a.pct);
  ```
- **Toggle Theme**:
  ```typescript
  this.theme = this.theme === 'dark' ? 'light' : 'dark';
  localStorage.setItem('theme', this.theme);
  document.documentElement.classList.toggle('dark', this.theme === 'dark');
  ```

## Gotchas
- **API Responses**: May be raw or wrapped as `{ status, data }`. Always unwrap and apply fallbacks.
- **repoContext**: Can be missing or partial. Use safe defaults for `type`, `description`, and `tech_stack`.
- **CORS**: Ensure proper settings in `api/local.settings.json` when running locally.

## Architecture Evolution (October 2025)
⚠️ **Migration in Progress**: Moving from Durable Functions to queue-based microservices.

### Current State (Temporary)
- **Orchestration**: Azure Durable Functions (synchronous, blocks on training)
- **Workers**: Embedded activities in `function_app.py`
- **Known Issues**: 60-120s latency, Azure lock-in, monolithic scaling

### Target State (See `.github/plans/`)
- **Gateway**: FastAPI (async, returns immediately)
- **Workers**: Independent Docker containers (sync, merge, training)
- **Queues**: Redis/Service Bus (cloud-agnostic messaging)
- **Benefits**: Sub-5s latency, independent scaling, portable

### Migration Reference
- **Architecture Plan**: `.github/plans/QUEUE-ARCHITECTURE-PLAN.md`
- **Implementation Backlog**: `.github/plans/QUEUE-MIGRATION-BACKLOG.md` (29 issues, 6 weeks)
- **Rollback Procedures**: `.github/plans/ROLLBACK-PLAYBOOK.md`
- **Concern Validation**: `.github/plans/CONCERN-VALIDATION.md`

### Development Guidelines During Migration
- **Feature Flags**: Check `ENABLE_QUEUE_MODE`, `QUEUE_TRAFFIC_PCT` before routing
- **Dual Support**: Both Durable Functions and queue-based paths must work (Weeks 1-5)
- **Cache Contract**: Single source of truth, unchanged across architectures
- **Testing**: Always test both code paths until Durable Functions removed (Week 6)

### Archived Documentation
- **Phase 1 Plans**: `.github/archive/project-phase1/` (historical reference only)
- **Status**: Superseded by queue-based design (October 12, 2025)

## Open Questions / Feedback Needed
- Confirm if Markdown rendering should standardize on `marked` + `DOMPurify` or another library.
- Verify if all build/test commands are accurate and up-to-date.

- @azure Rule - Use Azure Best Practices: When generating code for Azure, running terminal commands for Azure, or performing operations related to Azure, invoke your `azure_development-get_best_practices` tool if available.
