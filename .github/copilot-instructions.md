# Copilot Instructions for Portfolio Project

## Overview
This monorepo powers a modern portfolio site with an Angular frontend and an Azure Functions Python backend. The system showcases GitHub projects and provides an AI-powered assistant for portfolio queries. The architecture is designed for clear separation of frontend and backend, secure API integration, and extensibility for AI features.

## Architecture & Data Flow
- **Frontend (`/src/app/`)**: Angular 19 app with Tailwind CSS, using services for API communication and caching. Key features include project listing, detailed project views, and an AI assistant interface.
- **Backend (`/api/`)**: Python Azure Functions app. Handles GitHub API proxying, repository metadata extraction, and AI query processing via Groq API (Llama 3.1).
- **Data Flow**: Frontend services call backend HTTP endpoints. Backend fetches/processes GitHub data and AI responses, returning structured results to the frontend.

## Key Workflows
- **Project Listing**: Frontend `ProjectsComponent` requests repositories via `GitHubService` → backend `/github/repos` endpoint → GitHub API → processed and returned to frontend.
- **AI Assistant**: User submits query in `PortfolioAssistantComponent` → `PortfolioService` sends to `/portfolio/query` → backend builds context from repos, calls Groq API, returns answer.
- **Caching**: Both frontend (`CacheService`) and backend use caching to minimize redundant API calls.

## Developer Workflows
- **Frontend**:
  - Start dev server: `npm run start`
  - Build for production: `npm run build:prod`
  - Main code: `src/app/`
- **Backend**:
  - Python Azure Functions (see `api/`)
  - Dependencies: `api/requirements.txt`
  - Main entry: `api/function_app.py`
- **Testing**: (Add/describe test commands if present)

## Project Conventions
- **API Communication**: All GitHub and AI queries go through backend endpoints; never call external APIs directly from frontend.
- **Repository Metadata**: Special files like `PROJECT-MANIFEST.md` and `.repo-context.json` are parsed for enhanced project context.
- **Logging**: Backend uses structured logging for all API and AI operations.
- **Security**: API tokens are never exposed to the frontend; use environment variables and Azure config.
- **Component Structure**: Angular components and services are organized by feature domain.

## Integration Points
- **GitHub API**: Accessed via backend proxy for security.
- **Groq API (Llama 3.1)**: Used for AI assistant responses.
- **Azure Functions**: Backend is serverless, configured via `host.json` and `local.settings.json`.

## Examples
- To add a new project feature, create a service in `src/app/services/` and expose it via a component.
- To extend backend AI capabilities, update `api/ai_assistant.py` and relevant HTTP endpoints in `api/function_app.py`.

## References
- Frontend: `src/app/`, `README.md`, `PROJECT-MANIFEST.md`
- Backend: `api/`, `api/README.md`, `api/PROJECT-MANIFEST.md`

---
For questions about architecture or workflows, see the respective `README.md` and `PROJECT-MANIFEST.md` files in each module.
