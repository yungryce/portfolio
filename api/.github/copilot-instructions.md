# Portfolio API - Copilot Instructions

## Big Picture Architecture

Azure Functions Python app providing GitHub proxy + AI portfolio assistant. Uses **strict dependency injection** pattern across 3 layers:

**GitHub Layer**: `github/` - API client → Cache → FileManager → RepoManager (orchestrates all GitHub operations)  
**Application Layer**: `function_app.py` routes + `fa_helpers.py` response utilities  
**AI Layer**: `ai/` - Assistant → Scorer + ContextBuilder + QueryProcessor → Groq API

### Critical Dependency Order
```python
# Always initialize in this exact order
api = GitHubAPI(token=github_token, username=username)
cache = GitHubCache(use_cache=True)
file_manager = GitHubFileManager(api, cache)
repo_manager = GitHubRepoManager(api, cache, file_manager)
ai_assistant = AIAssistant(username=username, repo_manager=repo_manager)
```

## Essential Patterns

### Context Files Integration
- **`.repo-context.json`** - Critical for repository scoring/difficulty calculation. Contains `tech_stack`, `skill_manifest`, `project_identity`
- **Access pattern**: `extract_repo_data(repo, "repoContext.tech_stack.primary", [])` (dot notation for nested data)
- **Helper location**: `ai/helpers.py` - all context extraction utilities

### Standardized Response Patterns
```python
# Always use fa_helpers for responses
from fa_helpers import create_success_response, create_error_response
return create_success_response(data)  # Auto-adds cache headers
return create_error_response("message", 400)  # Standardized error format
```

### Logging Standard
Single logger: `logger = logging.getLogger('portfolio.api')`. Log business logic at INFO, data details at DEBUG. Always include context: `logger.info(f"Processing query for {username}: {query[:50]}")`
## AI Pipeline & Context Extraction

### AI Processing Flow
1. `repo_manager.get_all_repos_with_context(username, include_languages=True)` 
2. `extract_context_terms(query, repositories)` + `extract_language_terms(query)`
3. `repository_scorer.score_repositories(repositories, search_terms)`
4. `context_builder.build_enhanced_context(top_repos)`
5. `ai_query_processor.query_ai_with_context(context, query, fallback_used)`

### Repository Context Files (Critical)
- **`.repo-context.json`**: Enhanced metadata with `tech_stack.primary/secondary`, `skill_manifest.technical`, `project_identity.type`
- **`SKILLS-INDEX.md`**: Skills/technologies (passed to AI verbatim)  
- **`README.md`**: Descriptions (truncated via `truncate_text()`)
- **`ARCHITECTURE.md`**: Returned as metadata (not processed by AI)

## Developer Workflows

### Local Development
- **Start**: `func start` 
- **Logs**: Check `api_function_app.log` for detailed output
- **Test Architecture**: `python test_new_architecture.py`

### Environment Variables (Required)
- `GITHUB_TOKEN` - GitHub API access
- `GROQ_API_KEY` - AI processing  
- `AzureWebJobsStorage` - Cache storage connection string

### Key Routes
- `GET /github/repos/{username}` - List repos with language data
- `GET /github/repos/{username}/with-context` - Repos + enhanced metadata  
- `POST /portfolio/query` - AI query (requires JSON body with `query` field)
- `GET /repository/{repo}/difficulty` - Calculate and return repository difficulty using language data and context
- `POST /github/cache/cleanup` - Manual cache cleanup (supports `dry_run`, `batch_size`)

## Critical Implementation Notes

### Module Refactoring Status
⚠️ **Current AI module has deviations from original design**:
- `context_builder.py` - Now builds AI context (originally for `repoContext` scoring)
- `repository_scorer.py` - Misaligned with original goals
- `ai_query_processor.py` - Has duplicate `process_query()` function conflicting with `ai_assistant.py`

### Data Access Patterns
- **Safe extraction**: `extract_repo_data(repo, "repoContext.skill_manifest.technical", [])`  
- **Term filtering**: Import from `data_filter.py` - `technical_terms_structured`, `tool_ecosystems`
- **GitHub operations**: Use appropriate manager (RepoManager for metadata, FileManager for content, Cache for cleanup)