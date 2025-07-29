# Step-by-Step Guide: Parallelized Repository Context Retrieval with Azure Durable Functions

## 1. Understand the Current Data Flow
*** The function `get_all_repos_with_context` in `github_repo_manager.py` currently: ***
- Fetches all repositories for a user.
- For each repo, retrieves metadata, languages, `.repo-context.json`, and root file listing.
- This is done sequentially, causing latency.

## 2. Design for Parallel Execution
*** Use Azure Durable Functions to orchestrate parallel activities: ***
- Create an Orchestrator Function that:
  - Accepts a username.
  - Fetches the list of repository names.
  - For each repo, starts an Activity Function to:
    - Fetch repository metadata.
    - Fetch languages.
    - Fetch `.repo-context.json`.
    - Fetch file types (using logic from `ai_assistant.py`).
- All Activity Functions run in parallel, managed by the Durable Functions framework.

### Example Durable Function Plan:
*** For each repo in the user’s list: ***
- Orchestrator triggers parallel Activity Functions for:
  - Fetching metadata.
  - Fetching languages.
  - Fetching `.repo-context.json`.
  - Fetching file types.
- Aggregate results into a ready-to-use metadata structure.

## 3. Refactor get_all_repos_with_context
*** Refactor to: ***
- Move context retrieval logic into Durable Function Activities.
- Orchestrator collects results from all Activities.
- Store results in cache for fast access.
- Ensure the orchestrator returns a list of dicts, each containing:
  - Metadata, languages, context, file types.

### Pseudocode Outline:
```python
# Durable Functions Python SDK example
import azure.durable_functions as df

def orchestrator_function(context: df.DurableOrchestrationContext):
    username = context.get_input()
    repo_names = yield context.call_activity('GetRepoNamesActivity', username)
    tasks = []
    for repo_name in repo_names:
        tasks.append(context.call_activity('FetchRepoContextBundleActivity', {
            'username': username,
            'repo_name': repo_name
        }))
    results = yield context.task_all(tasks)
    # Save to cache here if needed
    return results

def fetch_repo_context_bundle_activity(input_data):
    username = input_data['username']
    repo_name = input_data['repo_name']
    # Fetch metadata, languages, .repo-context.json, file types
    ...
    return {
        "metadata": ...,
        "repoContext": ...,
        "file_types": ...,
        "languages": ...
    }
```

## 4. Trigger Context Retrieval on App Startup
*** Move context retrieval to an initialization step:***
- Use a health check endpoint or startup trigger in `function_app.py`.
- On cold start or health check, start the Durable Orchestrator Function.
- Store results in cache for subsequent requests.

### Example Integration:
In `function_app.py`:
- On startup or health check, start the Durable Orchestrator.
- Optionally, use a timer-triggered Durable Function to refresh cache periodically.

## 5. Expose Ready-to-Use Metadata for Scoring
*** When a user query arrives:***
- Use cached metadata (already includes file types, context, languages).
- Pass directly to calculate_repo_scores in `ai_assistant.py`.

## 6. Follow Project Conventions
- Use structured logging (portfolio.api logger).
- Use GitHubCache for all cache operations.
- Never expose secrets in responses.
- Use `create_error_response` and `create_success_response` for HTTP responses.

## 7. Testing and Validation
Add/modify tests in `test_new_architecture.py` to validate:
- Durable Function orchestration and parallel context retrieval.
- Cache population and usage.
- Correctness of metadata for scoring.

## Summary Table
Step	|   Action	| File(s)	|   Notes
1. | Analyze current sequential flow	| `github_repo_manager.py` | See get_all_repos_with_context
2. | Design Durable Function orchestration	| `function_app.py`, Durable Function files | Use Orchestrator and Activity Functions
3. | Refactor context retrieval	| Durable Function Activities | New orchestrator: parallel repo context retrieval
4. | Trigger on startup/health check	| `function_app.py` | Preload cache for fast queries
5. | Use cached metadata for scoring	| `ai_assistant.py` | Pass to calculate_repo_scores
6. | Follow conventions	| `copilot-instructions.md` | Logging, caching, error handling
7. | Test and validate	| `test_new_architecture.py` | Ensure correctness and performance

This approach will scale efficiently, reduce latency, and make repository metadata instantly available for scoring and AI queries in a production Azure Functions environment.