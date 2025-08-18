## Copilot instructions for this repository (Portfolio API)

Purpose: Make AI agents immediately productive in this Azure Functions (Python) backend that aggregates GitHub data, enriches it with AI, and serves HTTP endpoints. Keep guidance tied to the actual code here.

### Architecture overview
- Entry: `function_app.py` defines a Durable Functions app (`df.DFApp`) with HTTP routes, an orchestrator, activities, and a timer. Helpers live in `fa_helpers.py`.
- GitHub integration: `github/github_api.py` (REST) → `github/github_repo_manager.py` (metadata/context). Caching is centralized in `github/cache_manager.py` via a global `cache_manager` and decorators.
- Fingerprints: `github/fingerprint_manager.py` computes metadata/bundle hashes for change detection.
- AI: `ai/` modules (`ai_assistant.py`, `semantic_scorer.py`, `type_analyzer.py`, `ai_context_builder.py`, `repo_context_builder.py`) build tiered context and score repos. Groq is used through the OpenAI SDK with a custom base URL.

High‑level flow
1) Client starts the repo‑context orchestrator or calls the AI endpoint.
2) Orchestrator finds stale repos using fingerprints, fans out to fetch per‑repo bundles, and merges with any valid cached bundle.
3) AI ranks top repos and builds tiered context; HTTP helpers standardize responses.

### Read these files first
- `function_app.py`: routes; orchestrator `repo_context_orchestrator`; activities `get_stale_repos_activity`, `fetch_repo_context_bundle_activity`, `merge_repo_results_activity`.
- `fa_helpers.py`: `create_success_response`, `create_error_response`, `get_orchestration_status`, `trim_processed_repo`.
- `github/`: `github_api.py`, `github_repo_manager.py`, `cache_manager.py`, `fingerprint_manager.py`.
- `ai/`: `ai_assistant.py`, `semantic_scorer.py`, `type_analyzer.py`, `ai_context_builder.py`, `repo_context_builder.py`.

### HTTP API surface (as implemented)
- POST `/api/orchestrators/repo_context_orchestrator` — accepts `{ username, force_refresh }`; returns cached payload when bundle cache is valid.
- POST `/api/ai` — `{ query, username?, instance_id?, status_query_url? }`; uses cached bundle or orchestration output.
- GET `/api/github/repos/{username}` — list repos (+languages when requested).
- GET `/api/github/repos/{username}/{repo}` — single repo metadata (+languages).
- GET `/api/github/repos/{username}/{repo}/files?path=...` — returns decoded file text when `type=file`; otherwise `None`.
- GET `/api/github/repos/{username}/with-context` — trimmed repo metadata with context hints.
- POST `/api/github/cache/cleanup` — `{ dry_run, batch_size }`; GET `/api/github/cache/stats`.
- GET `/api/repository/{repo}/difficulty` — AI difficulty score for one repo.
Note: A health route exists in comments; it’s not currently active.

### Caching conventions (github/cache_manager.py)
- Azure Blob container: `github-cache`.
- Keys: bundle `repos_bundle_context_{username}`; per‑repo `repo_level_bundle_{username}_{repo}`; model `fine_tuned_model_metadata` or `model_{fingerprint}`.
- `get()` returns a `status` in `{ valid, missing, disabled, error, expired }` plus `fingerprint`, `last_modified`, `size_bytes` when available.
- `save(ttl=None)` defaults to no expiration; legacy tests may expect a `no_expiry` metadata that isn’t set now.
- If `AzureWebJobsStorage` is absent, caching is gracefully disabled.

### Manager wiring (what the code does)
```py
from github.github_api import GitHubAPI
from github.github_repo_manager import GitHubRepoManager

def _get_github_managers(username=None):
    api = GitHubAPI(token=os.getenv('GITHUB_TOKEN'), username=username)
    return GitHubRepoManager(api, username=username)
```
Cache is applied via `@cache_manager.cache_decorator(...)` inside manager methods; no cache instance is injected.

### AI pipeline highlights
- `FileTypeAnalyzer` classifies extensions using `linguist/languages.yml` and computes a weighted type score.
- `SemanticScorer` embeds/ranks signal, aggregates context + language + type scores.
- `RepoContextBuilder.build_tiered_context` collects README, SKILLS‑INDEX, ARCHITECTURE, and `.repo-context.json` if present.
- `AIContextBuilder` configures OpenAI SDK for Groq with `GROQ_API_KEY` and base URL.

### Conventions and gotchas
- Responses: use `create_success_response`/`create_error_response`. Prefer `handle_github_error(e)` for upstream failures.
- Logging: `logging.getLogger('portfolio.api')`; file path from `API_LOG_FILE` or defaults to `api_function_app.log`.
- Orchestrator handoff: when calling AI immediately after orchestration, include both `instance_id` and `status_query_url`.
- Defaults: many paths default `username` to `yungryce`; pass explicitly for multi‑user scenarios.
- Timer: schedule is `0 0 0 * * *` (midnight daily)

### Local workflows (Linux/bash)
- Python 3.11+, Azure Functions Core Tools installed; `pip install -r requirements.txt`.
- Env vars (local only; don’t commit): `AzureWebJobsStorage`, `GITHUB_TOKEN`, `GROQ_API_KEY`, optional `API_LOG_FILE`.
- Run locally: `func start`. End‑to‑end smoke test: `./starter.sh` (starts orchestration, polls, then calls `/api/ai`).
- Tests: `pytest`. Some tests reflect older manager signatures (expecting tuple returns from `_get_github_managers` and `no_expiry` metadata) — update mocks if interfaces change.

### Repo‑specific examples
- Read README text: `repo_manager.get_file_content('yungryce', 'some-repo', 'README.md')`.
- All repos with context: `repo_manager.get_all_repos_with_context('yungryce', include_languages=True)`.
- Kick off orchestration via HTTP: POST `/api/orchestrators/repo_context_orchestrator` with `{ "username": "yungryce" }`.


