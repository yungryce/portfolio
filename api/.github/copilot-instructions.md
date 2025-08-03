````markdown
# Copilot Instructions for Portfolio API

## Overview
This repository contains an Azure Functions-based backend API for a portfolio website. It integrates GitHub data and AI-powered portfolio assistance. The project is structured to ensure modularity, scalability, and maintainability.

## Architecture
### Key Components
- **Azure Functions**: Provides the serverless backend for API endpoints.
- **Durable Functions**: Orchestrates parallel processing of GitHub repositories.
- **GitHub Integration**: Fetches repository data using secure token authentication.
- **Cache Management**: Implements sophisticated caching for GitHub data with TTL and invalidation.
- **AI Assistant**: Processes natural language queries using Groq API and repository analysis.

### Data Flow
1. HTTP requests are received by Azure Functions.
2. GitHub data is fetched from cache if valid, otherwise from GitHub API.
3. Durable Functions orchestrate parallel processing of repository data.
4. AI components analyze repository content and process user queries.
5. Responses are returned to the frontend with appropriate caching headers.

### Manager Pattern
The codebase uses a manager pattern for dependency injection:
```python
def _get_github_managers(username=None):
    api = GitHubAPI(token=github_token, username=username)
    cache = GitHubCache(use_cache=True)
    file_manager = GitHubFileManager(api, cache)
    repo_manager = GitHubRepoManager(api, cache, file_manager, username=username)
    return api, cache, file_manager, repo_manager
```

## Durable Functions Orchestration
The API uses Azure Durable Functions to orchestrate parallel processing of GitHub repositories:

1. **Orchestrator Function**: `repo_context_orchestrator` coordinates the workflow.
2. **Activity Functions**:
   - `get_stale_repos_activity`: Identifies repositories needing processing.
   - `fetch_repo_context_bundle_activity`: Processes a single repository.
   - `merge_repo_results_activity`: Combines fresh and cached data.

Example orchestration pattern:
```python
@app.orchestration_trigger(context_name="context")
def repo_context_orchestrator(context):
    username = context.get_input()
    stale_repos_data = yield context.call_activity('get_stale_repos_activity', username)
    tasks = []
    for repo_metadata in stale_repos_data['stale_repos']:
        tasks.append(context.call_activity('fetch_repo_context_bundle_activity', {...}))
    stale_results = yield context.task_all(tasks)
    merged_results = yield context.call_activity('merge_repo_results_activity', {...})
    return merged_results
```

## Caching Strategy
The API implements a sophisticated caching mechanism:

1. **Cache Levels**:
   - Bundle cache: Complete set of repository data
   - Individual repository cache: Data for single repositories
   
2. **Cache Operations**:
   - Cache generation with TTL (12-24 hours)
   - Cache validation before use
   - Cache cleanup via timer trigger
   - Force refresh option

Example cache check:
```python
if not force_refresh:
    cache_entry = cache._get_from_cache(bundle_cache_key)
    if cache_entry['status'] == 'valid':
        return create_success_response({
            "status": "cached",
            "message": "Using cached repository data",
            # Additional metadata...
        })
```

## AI Components
The API includes AI capabilities for repository analysis:

1. **Query Processing**: `AIAssistant.process_query_results` handles natural language queries.
2. **File Type Analysis**: `FileTypeAnalyzer` categorizes repository files.
3. **Repository Difficulty Analysis**: Calculates difficulty scores for repositories.

## Developer Workflows
### Local Development
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Set up environment variables:
   ```bash
   export GITHUB_TOKEN=your_github_token
   export GROQ_API_KEY=your_groq_api_key
   ```
3. Run the Azure Functions locally:
   ```bash
   func start
   ```

### Testing
`./starter.sh` script runs tests:
```bash

## Error Handling Pattern
All endpoints follow a consistent error handling pattern:
```python
try:
    # Business logic
    return create_success_response(result)
except Exception as e:
    logger.error(f"Error description: {str(e)}")
    return create_error_response(f"User-facing message: {str(e)}", status_code)
```

## Logging
The API uses structured logging throughout:
```python
logger = logging.getLogger('portfolio.api')
logger.info(f"Meaningful message with context: {variable}")
logger.error(f"Error message: {str(e)}", exc_info=True)
```

## Integration Points
### GitHub API
- Authenticated via personal access token in environment variables.
- Rate limit handling and error management included.

### Groq API
- Used for AI query processing with Llama 3.1 model.
- API key stored in environment variables.

## Cache Management
- Periodic cleanup via timer trigger (`cache_cleanup_timer`).
- Manual cleanup endpoint (`/github/cache/cleanup`).
- Cache statistics endpoint (`/github/cache/stats`).
````

## Sentence Transformer
...
