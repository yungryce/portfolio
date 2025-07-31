# Copilot Instructions for Portfolio API

## Project Overview
This backend powers a portfolio website using Azure Functions, Python, and AI. It integrates GitHub data and Groq (Llama 3.1) for context-rich, secure, and scalable portfolio analysis. The design emphasizes modularity, caching, and context enrichment for high-performance AI queries.

## Architecture & Major Components
- **Azure Functions Entrypoint**: `function_app.py` defines HTTP endpoints and orchestrates request handling. All requests flow through this file.
- **GitHub Integration** (`github/`):
  - `github_api.py`: Handles direct GitHub API requests.
  - `github_repo_manager.py`: Manages repository metadata, context extraction, and caching. Use `get_all_repos_with_context` for all context-rich operations (deprecated: `get_all_repos_with_files`).
  - `github_file_manager.py`: Fetches file contents and directory listings from GitHub.
  - `cache_client.py`: Implements caching for API responses and file data. All GitHub data access should use this cache layer.
- **AI Orchestration** (`ai/`):
  - `ai_assistant.py`: Main orchestrator for repository scoring, context building, and AI query processing.
  - `ai_context_builder.py`: Builds tiered context for AI, manages Groq API calls, and enforces token limits. See `build_tiered_context`, `build_ai_query_context`, and `process_query_with_metadata` for core logic.
  - `semantic_scorer.py`, `type_analyzer.py`, `repo_context_builder.py`: Support context enrichment and scoring.
- **Helpers**: `fa_helpers.py` and `data_filter.py` provide response formatting, validation, and language extraction utilities. Always use `create_error_response` and `create_success_response` for HTTP responses.

## Data Flow
1. HTTP request received by Azure Function endpoint (`function_app.py`).
2. GitHub managers are initialized per request (see `_get_github_managers`).
3. Repository data is fetched, cached, and contextually enriched (including `.repo-context.json`, file listings, and scoring).
4. AI queries are processed using Groq API (Llama 3.1) with tiered, token-limited context (see `ai/ai_context_builder.py`).
5. Structured responses are returned to the frontend.

## Key Patterns & Conventions
- **Caching**: All GitHub API and file responses must use `GitHubCache` (see `github/cache_client.py`).
- **Context Enrichment**: Always use `get_all_repos_with_context` for repo context. Context is built from `.repo-context.json`, file listings, and scoring metadata.
- **Logging**: Use the `portfolio.api` logger. Logs are written to `api_function_app.log` (configurable via `API_LOG_FILE` env var).
- **Environment Variables**: Secrets (GitHub token, Groq API key) are loaded from environment variables. Never expose tokens in responses or logs.
- **Error Handling**: Use `create_error_response` and `create_success_response` from `fa_helpers.py` for all HTTP responses.
- **AI Query Processing**: Use `ai/ai_context_builder.py` for all Groq API calls. Enforce token and character limits using `ensure_context_size`.
- **Deprecation**: Do not use `get_all_repos_with_files` (deprecated).

## Developer Workflows
- **Local Development**:
  - Use Azure Functions Core Tools: `func start` (requires local.settings.json for env vars).
  - Set environment variables in `local.settings.json`.
- **Testing**:
  - Main tests: `tests/test_new_architecture.py`. Run with `pytest` from the repo root.
- **Dependencies**:
  - All Python dependencies are in `requirements.txt`. Do not manually add `azure-functions-worker`.
  - For CPU-only PyTorch, use the pinned wheel URL in `requirements.txt`.

## Integration Points
- **External APIs**:
  - GitHub API: All repository and file data.
  - Groq API: All AI-powered query processing (see `ai/ai_context_builder.py`).
- **Azure Services**:
  - Azure Functions: Main compute platform.
  - Azure Storage, Azure Monitor: Logging and telemetry.

## Project-Specific Examples
- Fetch all repositories with context:
  ```python
  repo_manager.get_all_repos_with_context(username="myuser")
  ```
- Process an AI query:
  ```python
  ai_assistant = AIAssistant(username="myuser", repo_manager=repo_manager)
  result = ai_assistant.process_query(query="Show me my Python projects")
  ```
- Fetch a file from a repo:
  ```python
  repo_manager.get_file_content(repo_name="myrepo", path="README.md")
  ```

## Directory References
- `function_app.py`: Azure Functions entrypoint and routing
- `github/`: GitHub API, repo management, caching, file access
- `ai/`: AI orchestration, context building, scoring
- `requirements.txt`: Python dependencies
- `local.settings.json`: Local environment config
- `Samples/`: Reference documentation and schema templates

## Additional Notes
- Follow the README.md template in `Samples/doc-schema/project/README.md` for documentation generation.
- For infrastructure or context extraction, see `Samples/repo-context/README.md` and `PROJECT-MANIFEST.md`.
- Always use structured logging and cache responses for performance.

---

*Ask for feedback if any section is unclear, incomplete, or missing critical project knowledge.*
