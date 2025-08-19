## Copilot instructions for this repository (Portfolio API)

Purpose: Equip AI agents to work productively in this Azure Functions (Python) backend that aggregates GitHub data, enriches it with AI, and serves HTTP endpoints. Keep guidance specific to this codebase.

### Architecture overview
- Entry: `function_app.py` declares a Durable Functions app (`df.DFApp`) with HTTP routes, one orchestrator, multiple activities, and a timer. Shared HTTP utilities live in `fa_helpers.py`.
- GitHub integration (under `config/`): `github_api.py` (GitHub REST), `github_repo_manager.py` (repo metadata, file content, trees, language stats). Caching is centralized in `config/cache_manager.py` via a global `cache_manager` and decorators.
- Fingerprints: `config/fingerprint_manager.py` computes per‑repo and bundle hashes for change detection.
- AI: `ai/ai_assistant.py` (Groq via OpenAI SDK), `ai/repo_scoring_service.py` (semantic + heuristic scoring), `ai/type_analyzer.py` (file type categorization via `linguist/languages.yml`). Fine‑tuning and model management live in `config/fine_tuning.py`.

High‑level flow
1) Client triggers the orchestrator or calls the AI endpoint.
2) Orchestrator identifies stale repos by comparing fingerprints, fans out per‑repo fetch + context build, then merges with any valid cached bundle.
3) A background activity ensures a semantic model is ready (fine‑tune or whiten embeddings) and the AI endpoint ranks repos and answers queries.

### Read these files first
- `function_app.py`: routes; orchestrator `repo_context_orchestrator`; activities `get_stale_repos_activity`, `fetch_repo_context_bundle_activity`, `merge_repo_results_activity`, `train_semantic_model_activity`.
- `fa_helpers.py`: `create_success_response`, `create_error_response`, `get_orchestration_status`, `trim_processed_repo`, `handle_github_error`.
- `config/`: `github_api.py`, `github_repo_manager.py`, `cache_manager.py`, `fingerprint_manager.py`, `fine_tuning.py`.
- `ai/`: `ai_assistant.py`, `repo_scoring_service.py`, `type_analyzer.py`.

### HTTP API surface (current code)
- POST `/api/orchestrators/repo_context_orchestrator` — body `{ username?, force_refresh? }`; returns cached payload immediately when bundle cache is valid, otherwise Durable Functions status response.
- POST `/api/ai` — `{ query, username?, instance_id?, status_query_url? }`; uses cached bundle or orchestrator output (requires both `instance_id` and `status_query_url` for best reliability).
- POST `/api/github/cache/cleanup` — `{ dry_run, batch_size }` to sweep expired entries.
- GET `/api/health` — returns environment and cache status.
Note: GitHub GET endpoints in the README aren’t wired in `function_app.py` at present.

### Caching conventions (`config/cache_manager.py`)
- Azure Blob container: `github-cache`. Disabled gracefully when `AzureWebJobsStorage` is not set.
- Keys: bundle `repos_bundle_context_{username}`; per‑repo `repo_level_bundle_{username}_{repo}`; model `fine_tuned_model_metadata` or `model_{fingerprint}`.
- `get()` returns `{ status: valid|missing|disabled|error|expired, data, fingerprint?, last_modified?, size_bytes? }`.
- `save(ttl=None)` persists JSON; fingerprints stored in blob metadata when provided. Legacy tests expect `no_expiry` metadata when `ttl=None` (current code does not set it).
- Decorator: `@cache_manager.cache_decorator(cache_key_func=..., ttl=...)` caches method results; decorator uses kwargs to build keys.

### Manager wiring (what the code actually does)
```py
from config.github_api import GitHubAPI
from config.github_repo_manager import GitHubRepoManager

def _get_github_managers(username=None):
    api = GitHubAPI(token=os.getenv('GITHUB_TOKEN'), username=username)
    return GitHubRepoManager(api, username=username)  # single manager, not a tuple
```
Use `GitHubRepoManager.get_all_repos_metadata(..., include_languages=True)` and `get_file_content(repo, path, username)`; repo trees via `get_repository_tree(..., recursive=True)`.

### Orchestration behavior
- Stale detection: `get_stale_repos_activity` fingerprints current metadata and compares against cached bundle fingerprints; falls back to per‑repo cache before marking stale.
- Per‑repo fetch: `fetch_repo_context_bundle_activity` loads `.repo-context.json`, `README.md`, `SKILLS-INDEX.md`, `ARCHITECTURE.md`; computes `file_types` and `categorized_types` via `FileTypeAnalyzer`; saves per‑repo cache with a fingerprint.
- Merge: `merge_repo_results_activity` updates cached items with fresh results, adds new ones, saves the merged bundle, and computes a bundle fingerprint.
- Model prep: `train_semantic_model_activity` fine‑tunes or applies whitening from `config/fine_tuning.py` when enough documented repos exist.
- Timer: `@app.timer_trigger('0 0 0 * * *')` runs daily to clean expired cache.

### AI pipeline highlights
- Scoring: `ai/repo_scoring_service.py` computes `context_score` (semantic embeddings), `language_score` (query language matches via `data_filter.extract_language_terms`), and `type_score` (file‑type weighting) → `total_relevance_score`.
- Assistant: `ai/ai_assistant.py` builds a tiered context from top repos and calls Groq via OpenAI SDK (`GROQ_API_KEY`, base_url `https://api.groq.com/openai/v1`). When the key is missing, it returns a structured “AI disabled” response.

### Conventions and gotchas
- Responses: always use `create_success_response`/`create_error_response`; for upstream GitHub failures, prefer `handle_github_error(e)`.
- Logging: logger name `portfolio.api`; file path from `API_LOG_FILE` (defaults to `api_function_app.log`).
- Defaults: many paths default `username` to `yungryce`; pass explicitly for multi‑user scenarios.
- Orchestrator handoff: when chaining to `/api/ai`, include both `instance_id` and `status_query_url`; utility `get_orchestration_status` can poll when only `instance_id` is available.
- Tests: some legacy tests expect `_get_github_managers` to return tuples and `no_expiry` cache metadata; update mocks/expectations when modifying interfaces.

### Local workflows (Linux/bash)
- Python 3.11+, Azure Functions Core Tools; install deps with `pip install -r requirements.txt`.
- Required env (local only; don’t commit): `AzureWebJobsStorage`, `GITHUB_TOKEN`, `GROQ_API_KEY`, optional `API_LOG_FILE`.
- Run locally: `func start`. Smoke test: `./starter.sh` (starts orchestration, polls, then posts to `/api/ai`).
- Tests: `pytest` (note legacy expectations as above).

### Repo‑specific examples
- Fetch README text: `repo_manager.get_file_content('yungryce', 'some-repo', 'README.md')`.
- List all repos + languages: `repo_manager.get_all_repos_metadata('yungryce', include_languages=True)`.
- Score repos for a query (within a function): `RepoScoringService(username).score_repositories(query, bundle)`.
- Trigger orchestration via HTTP: POST `/api/orchestrators/repo_context_orchestrator` with `{ "username": "yungryce" }`.

Questions or unclear bits? If you need the GitHub GET routes implemented or test expectations aligned (e.g., `no_expiry`), call it out and we’ll adjust the code or tests accordingly.


