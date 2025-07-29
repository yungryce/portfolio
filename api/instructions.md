## Refactoring the `ai/` Module for Direct Class Instantiation

This guide provides a step-by-step approach to refactor the `ai/` module so that, like the `github/` module, you can directly instantiate the target class (e.g., `AIAssistant`) without unnecessary side effects or extra setup. This aligns with project conventions and best practices described in `.github/copilot-instructions.md` and `instructions-old.md`.

### 1. **Understand the Current Structure**
- The `ai/` module contains several classes: `AIAssistant`, `SemanticScorer`, `FileTypeAnalyzer`, `RepoContextBuilder`, etc.
- Some classes may have implicit dependencies or initialization logic that makes direct instantiation cumbersome.

### 2. **Identify and Isolate Side Effects**
- Review all `__init__.py` and module-level code in `ai/` for side effects (e.g., global variables, logging setup, environment variable loading, or code that runs on import).
- Move any such logic inside class methods or under `if __name__ == "__main__":` blocks if only needed for scripts.

### 3. **Refactor Class Constructors**
- Ensure each class in `ai/` can be instantiated with only the required arguments, and does not perform unnecessary work on import.
- For example, `AIAssistant` should only initialize its dependencies (e.g., `repo_manager`, `semantic_scorer`, etc.) in its constructor, and not at the module level.
- Remove or refactor any code that instantiates classes or runs logic at the module level.

### 4. **Centralize Dependency Injection**
- Use explicit constructor arguments for dependencies (e.g., pass `repo_manager` to `AIAssistant`).
- Avoid hidden dependencies via global state or environment variables unless absolutely necessary (and document them clearly).
- If a class needs a dependency (like a logger or API key), pass it in or load it in the constructor, not at import time.

### 5. **Update Imports and Usage**
- In files that use `ai/` classes (e.g., `function_app.py`), update imports so you can do:
  ```python
  from ai.ai_assistant import AIAssistant
  ai = AIAssistant(username="myuser", repo_manager=repo_manager)
  ```
- Remove any unnecessary intermediate wrappers or factory functions unless they add value.

### 6. **Test for Import Safety and Direct Instantiation**
- After refactoring, you should be able to import any class from `ai/` without triggering side effects or requiring extra setup.
- Add or update tests to instantiate each class in isolation and verify expected behavior.

### 7. **Document the Refactored Pattern**
- In the module docstring or README, document the new pattern for instantiating and using `ai/` classes.
- Example:
  ```python
  from ai.ai_assistant import AIAssistant
  ai = AIAssistant(username="myuser", repo_manager=repo_manager)
  result = ai.process_query(query, repositories)
  ```

### 8. **Follow Project Conventions**
- Use structured logging via the `portfolio.api` logger.
- Use environment variables only for secrets, and never expose them in responses.
- Use the cache and error/success response helpers as described in `.github/copilot-instructions.md`.

### 9. **Validate with End-to-End and Unit Tests**
- Run all tests in `tests/` and add new ones as needed to cover direct instantiation and usage of `ai/` classes.
- Ensure that the refactor does not break existing API endpoints or workflows.

---

**Summary:**
Refactor the `ai/` module so that each class can be directly imported and instantiated with only the required arguments, with no side effects on import. This will make the codebase more modular, testable, and maintainable, and aligns with the architecture and conventions of the portfolio API project.
