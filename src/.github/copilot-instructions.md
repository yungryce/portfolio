# AI coding agent guide for this repo

Purpose: equip agents with specific, current patterns for the Angular frontend that consumes the Azure Functions API. Keep guidance concise and actionable.

## Architecture snapshot
- Angular (standalone components). Entry: `src/main.ts` with `bootstrapApplication`.
- Routes in `src/app/app.routes.ts`.
  - `/projects` → new dynamic grid from `app/projects` (uses RepoBundleService)
  - `/projects/:repo` → detail page from `app/projects/project`
  - `/assistant` → AI Q&A (POST `/api/ai`)
- Backend base URL via `ConfigService.apiUrl`:
  - dev: `http://localhost:7071/api`
  - prod: `/api`

## Data and services
- Use `RepoBundleService` (replace deprecated GithubService for projects views)
  - `getUserBundle(username)` → `{ username, data: Repo[] }`
  - `getUserSingleRepoBundle(username, repo)` → single `Repo`
- Card field mapping (no hardcoding):
  - Title → `name`
  - Updated → `metadata.updated_at`
  - Type → `repoContext.type || repoContext.project_identity.type || 'Unknown'`
  - Description → `repoContext.description || repoContext.project_identity.description || 'No description'`
  - Primary stack → `repoContext.tech_stack.primary ?? []`
  - Languages % → from `languages` map (sum bytes → percentage desc)

## Theming (dark/light) – global toggle
- Global theme is controlled by a `dark` class on `<html>`; persisted in `localStorage.theme`.
- Pages should:
  - On init: read `localStorage.theme` or `prefers-color-scheme`, then set `<html>.classList`.
  - Provide a toggle (button) that flips between `light` and `dark`, updates `localStorage`, and `<html>` class.
- Use CSS variables for tokens and pair with Tailwind utilities:
  - `--bg`, `--fg`, `--muted`, `--border`, `--card`, `--soft`, `--primary`, `--primary-foreground`, `--chip-bg`, `--chip-fg`, `--ring`.
  - Example in `app/projects/projects.component.css`. Prefer `bg-[var(--bg)] text-[var(--fg)]` etc.

## UI patterns (projects)
- Responsive grid: `grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6`.
- Card sections: header (name + updated), description (3-line clamp), tech chips, language bar + top labels.
- Skeletons: show 6+ placeholder cards using `animate-pulse` while loading.
- Accessibility: buttons have `aria-label`/`aria-pressed`; progress bar has `role="progressbar"`.

## Implementation references
- Component VM builder and filters: `app/projects/projects.component.ts` (`toCardVM`, filters, sort).
- Redesigned UI + theme toggle: `app/projects/projects.component.html/.css`.
- Config: `app/services/config.service.ts` (don’t hardcode API URLs).

## Gotchas
- API wrapper responses may be `{ status, data }` → service should unwrap to `{ username, data }`.
- `repoContext` may be partial/missing; always apply fallbacks.
- Large bundles: keep filtering/sorting client-side and efficient; avoid recomputing on every keystroke if perf drops.

## Quick tasks
- Add theme toggle to a new page: replicate `toggleTheme/initTheme/applyTheme` pattern; style with token vars.
- New card field: extend `RepoCardVM` and map from the bundle; keep layout consistent and accessible.
- Debug data shape: check Network tab; for backend, see `api/api_function_app.log`.
