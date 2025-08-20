Analyze this codebase to generate or update .github/copilot-instructions.md for guiding AI coding agents.

Focus on discovering the essential knowledge that would help an AI agents be immediately productive in this codebase. While using refactoring guide to ensure instructions meet current requirements
Consider aspects like:

The "big picture" architecture that requires reading multiple files to understand - major components, service boundaries, data flows, and the "why" behind structural decisions
"Refactoring Guide" which provides next step specifications on direction of `codebase`
Critical developer workflows (builds, tests, debugging) especially commands that aren't obvious from file inspection alone
Project-specific conventions and patterns that differ from common practices
Integration points, external dependencies, and cross-component communication patterns
Source existing AI conventions from **/{.github/copilot-instructions.md,AGENT.md,AGENTS.md,CLAUDE.md,.cursorrules,.windsurfrules,.clinerules,.cursor/rules/**,.windsurf/rules/**,.clinerules/**,README.md} (do one glob search).

Guidelines (read more at https://aka.ms/vscode-instructions-docs):

If .github/copilot-instructions.md exists, merge intelligently - preserve valuable content while updating outdated sections
Write concise, actionable instructions (~50-100 lines) using markdown structure
Include specific examples from the codebase when describing patterns
Avoid generic advice ("write tests", "handle errors") - focus on THIS project's specific approaches
Document only discoverable patterns, not aspirational practices
Reference key files/directories that exemplify important patterns

Refactoring Guide:
- `api` returns repo bundles (per repo or all repos) with which fields are dynamically mapped for `src/app/projects`
- `src/app/projects`: This displays repositories as cards with structured data fields for all returned repository in bundles. This consumes `api/function-app.get_repo_bundle`. Depracating `src/projects-old`
- `src/app/projects/project`: This displays a single repository bundle content. This cnsumes `api/function-app.get_single_repo_bundle. Depracating `src/projects-old/project-about`
- `src/assistant`: This displays returned ai response. This consumes `api/function-app.portfolio_query`. Depracating `src/portfolio-assistant`

Update .github/copilot-instructions.md for the user, then ask for feedback on any unclear or incomplete sections to iterate.