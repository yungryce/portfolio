Codebase New Direction: 
Due to repository scoring complexity previously implemented,  `Samples/old/repository_scorer.py` `Samples/old/helpers.py`, we would be moving in a new direction for the AI module.

Goal: Use Semantic Similarity Tool word comparison 
FLOW: 
- Retrieve user query and tokenize into words

Flow 1A:
- Retrieve .repo-context.json file for all repositories with their metadata. tokenize all repoContext values also into words
- Compare user query with each repoContext for similar words
- Aggregate scores for each repository and sort by highest score

Flow 1B:
- Compare each repository languages with user query 
- for repo with direct language matches, score using language byte size
- Score repositories and sort by highest score
- Use github linguists languages extracted to `linguist/languages.yml` to validate languages *if necesssary*

Flow 2:
- Aggregate 1A and 1B for each repository and standardize into total score 
- Using top scored repositories, Retrieve all file types and extensions in each repository by count. This must check all nested files and directories in repository (for example 3. constant can change)
- Use github linguists `linguist/languages.yml` to categorize all file types in each repository into programming, data, markup, prose or nil
- Score languages, and sum for each repository. Aggregate into total score
- New Score by type. Programming being the highest. Sum for each repository.
- Standardize with old total score and sort by highest

Flow 3:
- Retrieve final top repositories (for example 3. constant can change)
- Retrieve README.md, SKILLS-INDEX.md and ARCHITECHURE.md
- Build ai context for top 1 repository with README and SKILL-INDEX
-- Build smaller context with top 2 repositories 
- Return ai response on 3 repositories. 1st repo with detailed response, 2nd repo with less detail, last repo just mentioned

Semantic Similarity Tool Choice:
- Integrates seamlessly with function app
- open source/weight package/api 
- Lightweight implementation
- Proven scoring with high rating


Analyze `.github/copilot-instructions.md`, `ai/.github/copilot-instructions.md` and `instructions.md` to understand progress on codebase.
Analyze `instructions.md` for refactoring guide

Focus on discovering the essential knowledge that would help an AI agents be immediately productive in this codebase. Consider aspects like:
- The "big picture" architecture that requires reading multiple files to understand - major components, service boundaries, data flows, and the "why" behind structural decisions
- Critical developer workflows (builds, tests, debugging) especially commands that aren't obvious from file inspection alone
- Project-specific conventions and patterns that differ from common practices
- Integration points, external dependencies, and cross-component communication patterns

Source existing AI conventions from `**/{.github/copilot-instructions.md,ai/.github/copilot-instructions.md,instructions.md,AGENT.md,AGENTS.md,CLAUDE.md,.cursorrules,.windsurfrules,.clinerules,.cursor/rules/**,.windsurf/rules/**,.clinerules/**,README.md}` (do one glob search).

Guidelines (read more at https://aka.ms/vscode-instructions-docs):
- If `ai/.github/copilot-instructions.md` exists, merge intelligently - preserve valuable content while updating outdated sections
- Write concise, actionable instructions (~50-100 lines) using markdown structure
- Include specific examples from the codebase when describing patterns
- Avoid generic advice ("write tests", "handle errors") - focus on THIS project's specific approaches
- Document only discoverable patterns, not aspirational practices
- Reference key files/directories that exemplify important patterns

Update `ai/.github/copilot-instructions.md` for the user, then ask for feedback on any unclear or incomplete sections to iterate.


----------------------------------------------------------------------------------

-----------------------------------------------------------------------------------

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

----------------------------------------------------------------------------------

----------------------------------------------------------------------------------
# AI Module - Copilot Instructions

## Updated Pipeline Architecture

**Query Processing Flow**: AIAssistant → SemanticSimilarityScorer → RepositoryScorer → AIContextBuilder → AIQueryProcessor → Groq API

**Purpose**: This pipeline processes user queries by leveraging semantic similarity scoring, repository metadata, and AI-powered context building. Each component transforms raw data into actionable insights for the AI.

### Component Responsibilities
- **AIAssistant** (`ai/ai_assistant.py`) - Main coordinator, handles fallback logic, threshold filtering, and orchestrates the pipeline.
- **SemanticSimilarityScorer** (`ai/semantic_similarity_scorer.py`) - Compares user queries with repository metadata using a lightweight semantic similarity tool.
- **RepositoryScorer** (`ai/repository_scorer.py`) - Aggregates scores from semantic similarity and language-based scoring.
- **AIContextBuilder** (`ai/context_builder.py`) - Converts repository data into AI-consumable context strings.
- **AIQueryProcessor** (`ai/ai_query_processor.py`) - Interfaces with the Groq API, managing token limits (8K tokens, 25K chars).

## Updated Data Patterns

### Semantic Similarity Scoring
- **Query Tokenization**: Tokenize user queries into words.
- **Repository Metadata Tokenization**: Tokenize `.repo-context.json` values into words.
- **Scoring**: Compare tokenized query with repository metadata and aggregate scores.

### Language-Based Scoring
- **Language Matching**: Compare repository languages with user query.
- **Validation**: Use `linguist/languages.yml` to validate languages if necessary.
- **Scoring**: Score repositories based on language byte size and aggregate with semantic similarity scores.

### File Type Categorization
- **File Analysis**: Retrieve all file types and extensions in each repository, including nested files.
- **Categorization**: Use `linguist/languages.yml` to classify file types into programming, data, markup, prose, or nil.
- **Scoring**: Assign higher weights to programming files and aggregate scores.

## Fallback Logic
```python
RELEVANCE_THRESHOLD = 3.4  # Hard-coded in ai_assistant.py for testing
# If no repos meet threshold OR query lacks technical content → fallback strategy
fallback_used = True  # Top 3 Repos by scores passed to AI for context adjustment
```

## Integration Points

### Repository Manager Integration
- **Required**: Pass `repo_manager` to AIAssistant constructor for GitHub data access.
- **Method**: `repo_manager.get_all_repos_with_context(username, include_languages=True)`
- **Data Flow**: Repos → Semantic similarity scoring → Language-based scoring → File type categorization → Final scoring.

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
