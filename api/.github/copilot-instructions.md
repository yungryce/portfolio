# Copilot Instructions for Portfolio API

## Project Overview
This is an Azure Functions-based backend API for a portfolio website, integrating GitHub data and AI-powered assistance. The system is designed for secure, scalable, and context-rich portfolio analysis using Python, Azure, and external APIs.

## Architecture & Major Components
- **Azure Functions App** (`function_app.py`): Main entry point, defines HTTP endpoints and orchestrates request handling.
- **GitHub Integration** (`github/`):
  - `github_api.py`: Handles direct GitHub API requests.
  - `github_repo_manager.py`: Manages repository metadata, context extraction, and caching.
  - `github_file_manager.py`: Fetches file contents and directory listings from GitHub.
  - `cache_client.py`: Implements caching for API responses and file data.
- **AI Assistant** (`ai/`):
  - `ai_assistant.py`: Orchestrates repository scoring, context building, and AI query processing.
  - `semantic_scorer.py`, `type_analyzer.py`, `repo_context_builder.py`: Support context enrichment and scoring.
- **Helpers** (`fa_helpers.py`, `data_filter.py`): Utility functions for response formatting, validation, and language extraction.

## Data Flow
1. HTTP request received by Azure Function endpoint.
2. GitHub managers are initialized per request (see `_get_github_managers`).
3. Repository data is fetched, cached, and contextually enriched (including `.repo-context.json` and file listings).
4. AI queries are processed using Groq API (Llama 3.1) with enhanced context.
5. Structured responses are returned to the frontend.

## Key Patterns & Conventions
- **Caching**: All GitHub API and file responses are cached for performance. Use `GitHubCache` for all cache operations.
- **Context Enrichment**: Repository context is built from `.repo-context.json` and file listings. Always use `get_all_repos_with_context` for context-rich operations.
- **Logging**: Use the `portfolio.api` logger. Log files are written to `api_function_app.log` (configurable via `API_LOG_FILE` env var).
- **Environment Variables**: Secrets (GitHub token, Groq API key) are loaded from environment variables. Never expose tokens in responses.
- **Error Handling**: Use `create_error_response` and `create_success_response` from `fa_helpers.py` for all HTTP responses.
- **Deprecation**: Prefer `get_all_repos_with_context` over `get_all_repos_with_files` (the latter is deprecated).

## Developer Workflows
- **Local Development**:
  - Use Azure Functions Core Tools to run locally (`func start`).
  - Set environment variables in `local.settings.json`.
- **Testing**:
  - Tests are in `test_new_architecture.py`. Run with `pytest`.
- **Dependencies**:
  - All Python dependencies are in `requirements.txt`. Do not manually add `azure-functions-worker`.
  - For CPU-only PyTorch, use the pinned wheel URL in `requirements.txt`.

## Integration Points
- **External APIs**:
  - GitHub API: Used for all repository and file data.
  - Groq API: Used for AI-powered query processing.
- **Azure Services**:
  - Azure Functions: Main compute platform.
  - Azure Storage, Azure Monitor: Used for logging and telemetry.

## Project-Specific Examples
- To fetch all repositories with context:
  ```python
  repo_manager.get_all_repos_with_context(username="myuser")
  ```
- To process an AI query:
  ```python
  ai_assistant = AIAssistant(username="myuser", repo_manager=repo_manager)
  result = ai_assistant.process_query(query="Show me my Python projects")
  ```
- To fetch a file from a repo:
  ```python
  repo_manager.get_file_content(repo_name="myrepo", path="README.md")
  ```

## Directory References
- `function_app.py`: Azure Functions entrypoint and routing
- `github/`: GitHub API, repo management, caching, file access
- `ai/`: AI orchestration, context building, scoring
- `requirements.txt`: Python dependencies
- `local.settings.json`: Local environment config

## Additional Notes
- Follow the README.md template in `Samples/doc-schema/project/README.md` for documentation generation.
- For infrastructure or context extraction, see `Samples/repo-context/README.md` and `PROJECT-MANIFEST.md`.
- Always use structured logging and cache responses for performance.

---

*Ask for feedback if any section is unclear or missing critical project knowledge.*
