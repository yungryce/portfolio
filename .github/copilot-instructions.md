# Copilot Instructions for Portfolio Project

Concise, codebase-specific guidance.

## Big Picture
- Angular standalone + Tailwind (tokens in `src/styles.css`).
- Azure Functions backend in `api/` exposing bundles and AI endpoints.

## Bundles → UI mapping (no hardcoding)
- Title → `name`
- Updated → `metadata.updated_at`
- Type → `repoContext.type || repoContext.project_identity.type`
- Description → `repoContext.description || repoContext.project_identity.description`
- Primary stack → `repoContext.tech_stack.primary[]`
- Languages % → computed from `languages` byte map

## Refactor Direction
- `src/app/projects` uses `RepoBundleService.getUserBundle(username)`.
- `src/app/projects/project` uses `getUserSingleRepoBundle(username, repo)`.
- Deprecate `projects-old` and `project-about`. Prefer `RepoBundleService` over `GithubService`.

## Theming (dark/light)
- Global `<html>.dark` class toggled; tokens in `src/styles.css`:
  - `--bg`, `--fg`, `--muted`, `--border`, `--card`, `--soft`, `--primary`, `--primary-foreground`, `--chip-bg`, `--chip-fg`, `--ring`.
- On init: read `localStorage.theme` or `prefers-color-scheme`.
- Apply: add/remove `dark` on `<html>`, set `data-theme`.
- Use tokens in templates: `bg-[var(--bg)] text-[var(--fg)]`.
- Optional FOUC guard: inline preflight script in `src/index.html`.

## README rendering on project detail
- Render Markdown safely; build a linked Table of Contents.
- Use `marked` + `dompurify` in `ProjectComponent`:
  - Custom heading renderer injects ids and collects `{text,id,level}` for TOC.
  - Sanitize with DOMPurify, then set `[innerHTML]` via `DomSanitizer`.
- Template pattern:
  - Left TOC with anchor links (`href="#{id}"`), right content container with `[innerHTML]="readmeHtml"`.

## Navigation and Cards
- Each repo card links to details: `[routerLink]="['/projects', r.name]"`.
- GitHub button inside card uses `(click)="$event.stopPropagation()"`.
- Detail route param is `:repo`.

## Developer Workflows
- Frontend: `npm run start`.
- Backend: `cd api && pip install -r requirements.txt && func start`.
- API URL via `ConfigService.apiUrl` (dev `http://localhost:7071/api`).
- Logs: `api/api_function_app.log` for first-bundle dump.

## Endpoints
- `GET /bundles/{username}` → `{ username, data: Repo[] }`.
- `GET /bundles/{username}/{repo}` → `{ username, repo, data: Repo }`.
- `POST /ai` → assistant reply.

## Gotchas
- API may wrap payload as `{ status, data }` → unwrap in service.
- `repoContext` may be missing; use fallbacks.
- CORS: set in `api/local.settings.json`; restart `func start`.
