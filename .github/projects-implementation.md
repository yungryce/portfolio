# Dynamic Projects Implementation Guide

This guide explains how to implement the new dynamic Projects feature powered by the backend bundles API and the `RepoBundleService`. It replaces the deprecated `projects-old` module and the old `GithubService` for project listing.

## Objectives
- No hardcoded project data (do not use `src/app/projects-old/projects-config.ts`).
- Data source: `GET /bundles/{username}` and optionally `GET /bundles/{username}/{repo}`.
- Per-repo fields to render on the card:
  - `name`
  - `metadata.updated_at` (last updated)
  - `repoContext.type`
  - `repoContext.description`
  - `repoContext.tech_stack.primary[]`
  - `languages` as percentages
- UX features:
  - Dark and Light mode
  - Skeleton card grid before/during data retrieval
  - Tailwind CSS first, with vanilla CSS fallbacks when appropriate
  - Consistent alignment across cards

## Data Contract
The bundles API returns an object with `data` as an array. Each repo item includes at least:
- `name: string`
- `metadata.updated_at: string` (ISO date)
- `repoContext: object` with:
  - `type: string` (or fallback to `repoContext.project_identity.type` if not flattened)
  - `description: string` (or fallback to `repoContext.project_identity.description`)
  - `tech_stack.primary: string[]`
- `languages: Record<string, number>` (byte counts by language)

Reference example payload: see `api/api_function_app.log` (first repo object) and builder at `api/function_app.py:317-330`.

## Services
Use `src/app/services/repo-bundle.service.ts` (replaces deprecated `GithubService` for this feature):
- `getUserBundle(username: string): Observable<RepoBundleResponse>`
- `getUserSingleRepoBundle(username: string, repo: string): Observable<SingleRepoBundleResponse>` (optional detail view)

Remove `GithubService` imports/usages from the projects feature.

## New Component: Projects (replaces projects-old)
Create a standalone `ProjectsComponent` at `src/app/projects/` that:
- Calls `RepoBundleService.getUserBundle(username)`
- Derives a view model per repo
- Renders a responsive grid of cards using Tailwind classes, with CSS fallbacks

### Suggested View Model
```ts
interface RepoCardVM {
  name: string;
  updatedAt?: string;
  type: string;
  description: string;
  primaryStack: string[];
  languagesPct: { k: string; pct: number }[]; // sorted desc
}
```

### Language Percentages Helper
- Compute `total = sum(values(languages))` (guard with `|| 1`).
- Map entries to `pct = Math.round((bytes / total) * 100)`.
- Sort desc; optionally keep top 3–5 and group remainder as "Other".

## UI Requirements

### Grid and Alignment
- Responsive grid (Tailwind): `grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6`.
- Card sections: header (name + updated), description (3-line clamp), primary stack chips, language bar + labels.
- Clamp description to 3 lines to align card heights.


```css
:root { --bg:#fff; --fg:#0f172a; --muted:#64748b; --card:#f8fafc; --chip-bg:#e2e8f0; }
:root.dark { --bg:#0b1020; --fg:#e5e7eb; --muted:#94a3b8; --card:#111827; --chip-bg:#1f2937; }
```

### Loading Skeletons
- Show 6–9 skeleton cards before/during fetch.
- Tailwind utilities: `animate-pulse bg-gray-200 dark:bg-gray-700 rounded`.

### Tailwind + Vanilla CSS Fallbacks
Provide minimal CSS for features not covered by utilities:

```css
.repo-desc { display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; }
.lang-bar { height:6px; border-radius:4px; overflow:hidden; }
.lang-chunk { height:100%; display:inline-block; }
```

## Rendering Rules (mapping)
- Title: `name`
- Updated: `metadata.updated_at | date:'medium'`
- Type: `repoContext.type` (fallback to `repoContext.project_identity.type`; else `Unknown`)
- Description: `repoContext.description` (fallback to `repoContext.project_identity.description`; else `No description`)
- Primary stack chips: `repoContext.tech_stack.primary ?? []`
- Languages: computed percentages from `languages`

## Routing
- Update `app.routes.ts` to point to the new `ProjectsComponent` route (e.g., `/projects`).
- Remove routes referencing `src/app/projects-old`.

## Migration Steps
1. Create `src/app/projects/` and add a standalone `ProjectsComponent` (TS/HTML/CSS).
2. Inject and use `RepoBundleService` to fetch bundles.
3. Build the view model and render cards per the mappings above.
4. Implement skeleton grids while `repos$` is loading.
5. Add dark/light styling via Tailwind and CSS variable fallbacks.
6. Replace imports/usages of `GithubService` with `RepoBundleService` in the projects feature.
7. Remove or archive `src/app/projects-old/` after verification.

## Example Snippets

TS derivation (sketch):
```ts
repos$ = this.repoBundle.getUserBundle(this.username).pipe(
  map(b => (b?.data ?? []).map(r => this.toCardVM(r)))
);

private toCardVM(r: any): RepoCardVM {
  const pid = r?.repoContext?.project_identity ?? {};
  const type = r?.repoContext?.type ?? pid?.type ?? 'Unknown';
  const description = r?.repoContext?.description ?? pid?.description ?? 'No description';
  const langs = r?.languages ?? {};
  const total = Object.values(langs).reduce((a: number, b: number) => a + Number(b), 0) || 1;
  const languagesPct = Object.entries(langs)
    .map(([k, v]) => ({ k, pct: Math.round((Number(v) / total) * 100) }))
    .sort((a, b) => b.pct - a.pct);
  return {
    name: r?.name ?? 'unknown',
    updatedAt: r?.metadata?.updated_at,
    type,
    description,
    primaryStack: r?.repoContext?.tech_stack?.primary ?? [],
    languagesPct,
  };
}
```

Template highlights:
```html
<!-- Skeletons -->
<div *ngIf="!(repos$ | async)" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
  <div *ngFor="let i of [0,1,2,3,4,5]" class="p-4 rounded shadow animate-pulse bg-gray-100 dark:bg-gray-800">
    <div class="h-5 w-1/2 rounded bg-gray-200 dark:bg-gray-700 mb-3"></div>
    <div class="h-4 w-full rounded bg-gray-200 dark:bg-gray-700 mb-2"></div>
    <div class="h-4 w-5/6 rounded bg-gray-200 dark:bg-gray-700 mb-4"></div>
    <div class="h-6 w-2/3 rounded bg-gray-200 dark:bg-gray-700"></div>
  </div>
</div>

<!-- Cards -->
<div *ngIf="repos$ | async as repos" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
  <article *ngFor="let r of repos; trackBy: trackByName" class="rounded border shadow bg-white dark:bg-[var(--card)] text-[var(--fg)]">
    <header class="p-4 flex items-start justify-between">
      <h3 class="text-lg font-semibold">{{ r.name }}</h3>
      <time class="text-xs text-slate-500" [attr.datetime]="r.updatedAt">{{ r.updatedAt | date:'medium' }}</time>
    </header>
    <div class="px-4 pb-4">
      <p class="repo-desc text-sm text-slate-600 dark:text-slate-300">{{ r.description }}</p>
      <div class="mt-3 flex flex-wrap gap-2">
        <span *ngFor="let tech of r.primaryStack" class="px-2 py-1 text-xs rounded bg-[var(--chip-bg)] dark:bg-slate-700">{{ tech }}</span>
      </div>
      <div class="mt-4">
        <div class="lang-bar bg-slate-200 dark:bg-slate-700">
          <span *ngFor="let l of r.languagesPct" class="lang-chunk" [style.width.%]="l.pct" [attr.aria-label]="l.k + ' ' + l.pct + '%'" [title]="l.k + ' ' + l.pct + '%'" style="background: var(--chip-bg);"></span>
        </div>
        <div class="mt-2 flex flex-wrap gap-2 text-xs text-slate-600 dark:text-slate-300">
          <span *ngFor="let l of r.languagesPct | slice:0:3">{{ l.k }} {{ l.pct }}%</span>
        </div>
      </div>
    </div>
  </article>
</div>
```

## QA Checklist
- [ ] No hardcoded project metadata; all data sourced from bundles.
- [ ] Cards show name, updated date, type, description, primary stack, language %.
- [ ] Dark/light mode styles apply correctly.
- [ ] Skeletons are visible before/during fetch.
- [ ] Descriptions clamped to 3 lines; card heights align.

## Troubleshooting
- 404 bundle: ensure cache is populated and `/bundles/{username}` is correct.
- Missing `repoContext` fields: show fallbacks; do not break layout.
- Backend health: check `/health` endpoint, `GITHUB_TOKEN`, and storage config.
