# AI coding agent guide for this codebase

Purpose: Give AI agents the exact project patterns, data flows, and conventions used here so they can ship changes safely and fast. This is an Angular SPA that talks to an Azure Functions API.

## Big picture architecture
- Angular 17+ with standalone components. Entry: `main.ts` → `bootstrapApplication(AppComponent, appConfig)`.
- Routing (`app/app.routes.ts`):
  - `/` → `HomeComponent`
  - `/projects` → `ProjectsComponent` (list/grid)
  - `/projects/:repo` → `ProjectComponent` (detail + README)
  - `/assistant` → `AssistantComponent` (AI Q&A)
  - `**` → redirect to `/`
- API base URL is centralized in `ConfigService.apiUrl` and comes from `environments/*`:
  - dev: `http://localhost:7071/api`
  - prod: `/api`
- Styling uses Tailwind v4 via `@import 'tailwindcss'` and CSS variables. Global design tokens live in `styles.css`; pages/components consume them via utility classes like `bg-[var(--bg)]`.

## Key folders and files
- Bootstrapping: `main.ts`, `app/app.config.ts` (providers, HttpClient, MarkdownModule, optional app initializer)
- Routing: `app/app.routes.ts`
- Shell: `app/app.component.*`
- Environments: `environments/environment(.development).ts`
- Services: `app/services/*` (Config, RepoBundle, Assistant, Cache)
- Features:
  - Projects list: `app/projects/projects.component.*`
  - Project detail: `app/projects/project/project.component.*`
  - AI assistant: `app/assistant/assistant.component.*`

## Services and data shapes
- Repo bundle service (`RepoBundleService`)
  - `getUserBundle(username, useCache?)` → normalizes to `{ username, data: any[] }` and caches for ~10 min.
  - `getUserSingleRepoBundle(username, repo, useCache?)` → `{ username, repo, data: any }` (single repo bundle), cached.
  - Both unwrap `{ status: 'success', data: ... }` responses and fall back to safe defaults on errors.
- AI assistant service (`AIAssistantService`)
  - `askPortfolio({ query, username? })` → POST `${apiUrl}/ai` and returns `{ response: markdown, repositories_used, total_repositories, query }`.
  - Errors return a canned message, never throw to the UI.
- Config service (`ConfigService`)
  - Source of truth for `apiUrl` (use this, never hardcode).
- Cache service (`CacheService`)
  - Simple in-memory TTL cache: default 15 min, background cleanup every 5 min. Use string keys like `bundle-${username}`.

## UI/view-model conventions
- List/grid (Projects):
  - Build a thin view model (`toCardVM`) from bundle items: title from `name`, updated from `metadata.updated_at||pushed_at`, type/description from `repoContext.*` or `project_identity.*` with fallbacks, primary stack from `repoContext.tech_stack.primary`, language percentages from `languages` map (bytes → %). See `projects.component.ts`.
  - Filters: by search, language, technology, plus show/hide forks. Sorting by updated/name with asc/desc toggle. See `filterAndSortVMs`.
  - Accessibility: theme toggle uses `aria-pressed`, language bar uses `role="progressbar"`; cards are article elements with clear titles.
- Detail (Project):
  - Pull a single repo bundle, map to `RepoDetailVM`, render README markdown. Build a TOC by post-processing headings and assigning stable slug IDs. See `project.component.ts`.
- Assistant: Render markdown safely using `marked` → `DOMPurify` → `bypassSecurityTrustHtml`. Keep all user content sanitized.

## Theming (dark/light)
- Single global toggle based on the `dark` class on `<html>` and persisted in `localStorage.theme`.
- Pattern per component:
  - On init: read `localStorage.theme` or `prefers-color-scheme` → set `this.theme` and call `applyTheme`.
  - Toggle: flip `this.theme`, write to localStorage, call `applyTheme` which adds/removes `html.dark` and sets `data-theme`.
- Tokens you can rely on: `--bg`, `--fg`, `--muted`, `--border`, `--card`, `--soft`, `--primary`, `--primary-foreground`, `--chip-bg`, `--chip-fg`, `--ring` (see `styles.css` + component CSS).

## Integration points (API contracts)
- Bundles
  - `GET {apiUrl}/bundles/{username}` → `{ status?: 'success', data: { username, data: any[] } | any[] }`
  - `GET {apiUrl}/bundles/{username}/{repo}` → `{ status?: 'success', data: { username, repo, data } | any }`
  - Services are resilient to all of the above and cache normalized shapes.
- AI
  - `POST {apiUrl}/ai` with `{ query, username? }` → `{ response: markdown, repositories_used: {name,relevance_score}[] }`

## Patterns to follow when adding code
- New API calls: inject `HttpClient` + `ConfigService`; build URLs from `config.apiUrl`; unwrap `{ status, data }`; return safe defaults on `catchError`; add 10–15 min cache where beneficial.
- New list UIs: derive a typed VM with explicit fallbacks; use `async` pipe for observable streams when possible; keep filters/sorting pure and side-effect free.
- Markdown rendering: always sanitize with DOMPurify before trusting HTML; if you add anchors/TOC, generate slug IDs consistently.
- Do not hardcode styles; use CSS vars with Tailwind utilities (`bg-[var(--bg)] text-[var(--fg)]`, etc.).

## Developer workflows (what we know from this repo)
- This `src/` tree is Angular; build tooling (package.json/angular.json) may live in the parent repo. Typical flows (verify in the parent):
  - Dev server: `ng serve` or `npm run dev` from the project root.
  - Production build: `ng build` or `npm run build`.
  - API during dev: Azure Functions expected at `http://localhost:7071/api` (set via `environment.development.ts`).
- Tailwind v4 is used via `@import 'tailwindcss'` in `styles.css`; a separate tailwind.config.js may not exist.

## Examples (copy/paste patterns)
- Use RepoBundleService in a component:
  - `this.repoBundle$ = this.repoSvc.getUserBundle('yungryce');`
  - `this.filtered$ = this.repoBundle$.pipe(map(b => b.data.map(toCardVM)))`.
- Normalize a languages map to percentages:
  - `const total = Object.values(langs).reduce((a,b)=>a+Number(b),0)||1; Object.entries(langs).map(([k,v])=>({k,pct:Math.round(Number(v)/total*100)})).sort((a,b)=>b.pct-a.pct)`.
- Toggle theme:
  - `this.theme = this.theme==='dark'?'light':'dark'; localStorage.setItem('theme', this.theme); document.documentElement.classList.toggle('dark', this.theme==='dark');`

## Gotchas and guardrails
- API responses vary between raw and `{ status, data }`; always unwrap before use.
- `repoContext` can be missing/partial. Apply safe fallbacks for `type`, `description`, `tech_stack`.
- Cache keys must be unique and stable (`bundle-${username}`, `repo-bundle-${username}-${repo}`) and respect TTL; clear on data shape changes.
- Keep UI accessible: preserve aria attributes and roles already used in templates.

## Open questions / confirm with maintainers
- Build/test commands live outside this `src/` folder; confirm exact scripts in the repository root (Angular CLI vs. Vite).
- MarkdownModule is provided app-wide but most rendering uses `marked` + `DOMPurify`. If you standardize on one approach, update this guide.

If any section is unclear or incomplete (especially dev commands or API nuances), tell me and I’ll refine this doc.
