# AI Module - Copilot Instructions

## Pipeline Architecture

**Query Processing Flow**: AIAssistant → RepoContextBuilder → RepositoryScorer → DifficultyProcessor → AIContextBuilder → AIQueryProcessor → Groq API

**Purpose**: This pipeline is designed to process user queries by leveraging repository metadata and AI-powered scoring. Each component plays a specific role in transforming raw data into actionable insights for the AI.

### Component Responsibilities
- **AIAssistant** (`ai/ai_assistant.py`) - Main coordinator, handles fallback logic, threshold filtering, and orchestrates the pipeline.
- **RepoContextBuilder** - (`ai/repo_context_builder.py`) - Extracts repository data from `repoContext.get()` into consumable context for scoring and difficulty processing.
- **RepositoryScorer** (`ai/repository_scorer.py`) - Calculates relevance scores using metadata, technical skills, and project components.
- **DifficultyProcessor** - (`ai/difficulty_processor.py`) - Determines repository difficulty based on weighted scores.
- **AIContextBuilder** (`ai/context_builder.py`) - Converts repository data into AI-consumable context strings.
- **AIQueryProcessor** (`ai/ai_query_processor.py`) - Interfaces with the Groq API, managing token limits (8K tokens, 25K chars).

## Critical Data Patterns

### Context File Structure
```python
# Always use extract_repo_data() for safe access
tech_stack = extract_repo_data(repo, "repoContext.tech_stack.primary", [])
skills = extract_repo_data(repo, "repoContext.skill_manifest.technical", [])
project_type = extract_repo_data(repo, "repoContext.project_identity.type")
```
- **Why**: Ensures safe and consistent access to nested data in `.repo-context.json`.

### Search Term Extraction
- **Language terms**: `extract_language_terms(query)` - Extracts language terms from repository metadata and validate  `data_filter.py` constants.
- **Context terms**: `extract_context_terms(query, repositories)` - Dynamically retrieves repoContext fields, tokenizes them into words and structure for ease of comparison and scoring.
- **Context terms**: Search terms comparison with user query for matches Language and Context terms make up Search terms
- **Scoring**: Categories are weighted (e.g., language: 10.0 base, tech: varies by match type).

### Fallback Logic
```python
RELEVANCE_THRESHOLD = 3.4  # Hard-coded in ai_assistant.py for testing
# If no repos meet threshold OR query lacks technical content → fallback strategy
fallback_used = True  # Top 5 Repos by scores or difficulty passed to AI for context adjustment
```
- **Old fallback implementation**: `get_fallback_repositories()`

## Key Integration Points

### Repository Manager Integration
- **Required**: Pass `repo_manager` to AIAssistant constructor for GitHub data access.
- **Method**: `repo_manager.get_all_repos_with_context(username, include_languages=True)`
- **Data Flow**: Repos → Language processing → Context extraction → Scoring → Difficulty grading.

### Context Files (Must Include)
- **`.repo-context.json`**: Primary metadata source - tech_stack, skill_manifest, project_identity.
   - **Sample Context File**: `Samples/repo-context/.repo-context.json`
- **`README.md`**: Truncated descriptions via `truncate_text()`.
   - **Sample README.md**: `Samples/repo-context/README.md`
- **`SKILLS-INDEX.md`**: Passed verbatim to AI context.
   - **Sample SKILLS-INDEX.md**: `Samples/repo-context/SKILLS-INDEX.md`
- **`ARCHITECTURE.md`**: Metadata only (not AI processed).
   - **Sample ARCHITECTURE.md**: `Samples/repo-context/ARCHITECTURE.md`

## Known Deviations & Refactoring Issues

⚠️ **Current AI module imports from `Samples/new/` - temporary implementation**
- **Issue**: Original design in `Samples/old/` used direct GitHub client dependency. The new version uses the `repo_manager` pattern but components need alignment.
- **Conflict**: `ai_query_processor.py` has duplicate `process_query()` method (conflicts with `AIAssistant.process_query`).

### Actionable Steps
1. **Align Components**: Refactor `ai_query_processor.py` to remove duplicate methods and ensure compatibility with `AIAssistant`.
2. **Standardize Imports**: Transition all imports to the finalized `ai/` directory.
3. **Test Refactored Pipeline**: Use `test_new_architecture.py` to validate changes.
4. **Document Changes**: Update this file and related documentation to reflect the refactored design.