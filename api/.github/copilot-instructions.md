````markdown
## Copilot instructions for this repository (Portfolio API)

Purpose: Help AI agents contribute productively to this Azure Functions (Python) backend that aggregates GitHub data, enriches it with AI, and exposes HTTP endpoints. Keep answers grounded in the actual patterns and files below.

### Big picture architecture
- Entry point: `function_app.py` defines an Azure Durable Functions app (`DFApp`) with HTTP routes, an orchestrator, activities, a timer, and helpers from `fa_helpers.py`.
- GitHub integration: A small “managers” stack wires dependencies in order:
    - `github/github_api.py` (raw GitHub REST calls) → `github/cache_manager.py` (Azure Blob cache) → `github/github_repo_manager.py` (repo metadata + context).
- Caching: `CacheManager` stores JSON in Azure Blob Storage container `github-cache` with fingerprint metadata, status, and cleanup utilities.
- Fingerprint management: `FingerprintManager` handles content fingerprinting for change detection and cache invalidation.
- Github management: `GithubRepoManager` handles github operations management for all repositories
- AI enrichment: `ai/` modules score repositories and build query context using sentence-transformers and Groq via the OpenAI SDK pointed at Groq’s base URL.

High-level data flow
1) Client POSTs to start orchestration or directly queries AI.
2) The Durable orchestrator finds stale repos, fan-outs work to fetch per-repo bundles, then merges with cached bundles.
3) AI ranks top repos and builds tiered context; result or status is returned via HTTP helpers with caching headers.

### Key files to read first
- `function_app.py` — routes, orchestrator `repo_context_orchestrator`, activities: `get_stale_repos_activity`, `fetch_repo_context_bundle_activity`, `merge_repo_results_activity`.
- `fa_helpers.py` — `create_success_response`, `create_error_response`, `get_orchestration_status`, `trim_processed_repo`.
- `github/` — manager (`GithubRepoManager`), cache (`CacheManager`) and fingerprint (`FingerprintManager`).
- `ai/` — `ai_assistant.py`, `semantic_scorer.py`, `type_analyzer.py`, `ai_context_builder.py`.
- `model/` - model tuning `fine_tuning.py`

### HTTP surface (function_app.py)
- POST `/api/orchestrators/repo_context_orchestrator` — start orchestration; honors `{ username, force_refresh }`. If bundle cache is valid, returns cached payload immediately.
- POST `/api/ai` — body: `{ query, username?, instance_id?, status_query_url? }`; uses cached bundle or waits for orchestration completion to process query.
- GET `/api/github/repos/{username}` — list repos (+languages when enabled).
- GET `/api/github/repos/{username}/{repo}` — single repo metadata (+languages).
- GET `/api/github/repos/{username}/{repo}/files?path=...` — file or directory listing/content.
- GET `/api/github/repos/{username}/with-context` — metadata + `.repo-context.json` + root file paths.
- POST `/api/github/cache/cleanup` — `{ dry_run, batch_size }`.
- GET `/api/github/cache/stats`.
- GET `/api/repository/{repo}/difficulty` — AI difficulty analysis.
- GET `/api/health` — checks GitHub connectivity, cache, GROQ, storage.

Route notes
- Azure Functions app-level prefix `/api` is implied by Functions runtime.
- All routes intends to use bundles returned after orchestration. Not yet implemented

### Caching conventions (github/cache_client.py)
- Container: `github-cache`. 
    - Bundle: `repos_bundle_context_{username}`
    - Per-repo: `repo_context_{username}_{repo}`
    - model-tuning: `fine_tuned_model_metadata`, `{model_id}.zip`
- `get` returns `status` in `{ valid, invalid, missing, disabled, error }` and metadata including `fingerprint`, `size_bytes`.
- If `AzureWebJobsStorage` is missing, cache is disabled gracefully.

### Manager pattern (dependency order)
```py
from github.github_api import GitHubAPI
from github.cache_manager import CacheManager
from github.github_repo_manager import GitHubRepoManager
from github.fingerprint_manager import FingerprintManager

def _get_github_managers(username=None):
        api = GitHubAPI(token=os.getenv('GITHUB_TOKEN'), username=username)
        cache = CacheManager(use_cache=True)
        repo_manager = GitHubRepoManager(api, cache, username=username)
        fingerprint_manager = FingerPrintManager()
        return api, cache, repo_manager, fingerprint_manager
```

### AI pipeline highlights (ai/)
- Scoring: `SemanticScorer` embeds an enriched query and flattened repo context, computes cosine similarity, and aggregates with language/type scores.
- File-type signal: `FileTypeAnalyzer` classifies extensions using `linguist/languages.yml` and computes a weighted type score.
- Context: `RepoContextBuilder.build_tiered_context` collects README, SKILLS-INDEX, ARCHITECTURE, and repoContext for top repos.
- Groq: `AIContextBuilder` initializes OpenAI client with `base_url=https://api.groq.com/openai/v1` and `GROQ_API_KEY` (responses capped by token/char guards).

### Response and error conventions
- Use `create_success_response(data, cache_control)` and `create_error_response(message, status_code)` from `fa_helpers.py` (JSON, sensible headers).
- For upstream GitHub failures, prefer `fa_helpers.handle_github_error(e)` status mapping (401/403/404/429/5xx) instead of ad-hoc codes.
- Logging: always `logging.getLogger('portfolio.api')`; file logs go to `API_LOG_FILE` or default `api_function_app.log`.

### Local workflows (Linux/zsh)
- Python: 3.11+ recommended. Install: `pip install -r requirements.txt`.
- Required env (local only — do NOT commit secrets): `AzureWebJobsStorage`, `GITHUB_TOKEN`, `GROQ_API_KEY`, optional `API_LOG_FILE`.
- Start Functions: `func start` from repo root. Health at `/api/health`.
- Orchestration + AI smoke test: run `./starter.sh` to start the repo-context orchestrator, poll until complete or use cache, then POST to `/api/ai`.
- Tests: `pytest`. Note: some tests mock older activity signatures — update tests if activities change (see `tests/test_function_app.py`).
- Api Tests: Currently uses `starter.sh` for end to end tests.

### Project-specific patterns and gotchas
- Bundle-first: endpoints prefer the bundle cache; orchestration only fans out for stale/missing repos.
- `.repo-context.json` drives AI context; missing/invalid JSON is tolerated with warnings and empty context.
- File listings: `GitHubRepoManager.get_file_content` returns either decoded file text or a directory listing (list of metadata dicts) — check type before use.
- Durable status: when invoking AI right after orchestration, pass `instance_id` and `status_query_url` so the AI endpoint can fetch results if not cached.
- Security: use env vars for tokens/keys; never hardcode. `local.settings.json` is for local dev only — scrub secrets before commit.

### Handy examples tied to this repo
- Fetch a repo file’s text: `repo_manager.get_file_content('some-repo', 'README.md', username)`.
- Get all repos with context: `repo_manager.get_all_repos_with_context(username, include_languages=True)`.
- Kick off orchestration (HTTP): POST `http_start` and `/api/orchestrators/repo_context_orchestrator` with `{ "username": "yungryce" }`.

Feedback needed
- Are any endpoints undocumented or renamed? Is the timer cadence intended to be hourly? If you need edits to activity inputs/outputs documented more formally (contracts), tell me and I’ll add them.
