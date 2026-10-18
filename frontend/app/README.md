# my.minmatar.org frontend

The Astro site at [my.minmatar.org](https://my.minmatar.org/). Pages are rendered on the server; htmx swaps in server-rendered partials, and Alpine.js handles small local UI state. It talks to the Django API in `backend/`.

Read [docs/frontend-design.md](../../docs/frontend-design.md) before changing UI code. It is the source of truth for the htmx/Alpine split, design tokens, layout compositions and component conventions. [AGENTS.md](AGENTS.md) has the short version.

## Setup

Use Node 22 (newer majors break `npm i`; see [Toolchain versions](../../README.md#toolchain-versions)). From the repo root:

```bash
cp frontend/.env.example frontend/app/.env
cd frontend/app
npm i
npm run dev        # http://localhost:4321, against the API in API_URL
```

`./dev.sh` at the repo root starts the frontend together with the API and Celery.

## Commands

Run from `frontend/app/`:

| Command | What it does |
| --- | --- |
| `npm run dev` | Dev server on port 4321 |
| `npm run check` | Type-check ratchet (`scripts/check_ratchet.mjs`): runs `astro check` and fails only when a file has more errors than its entry in `testing/conventions/type_check_baseline.json` (new files: zero). Must pass before a frontend change merges |
| `npm run check:baseline` | Rewrite that baseline after fixing errors, to lock the gain in (the baseline only shrinks) |
| `npm run test` | vitest (tests live in `testing/`) |
| `npm run build` | Type check, then production build |
| `npm run warzone:extract` / `npm run amamake:extract` | Data extraction for the monthly Warzone and Amamake reports |

`check`, `test` and `build` load `.env.BUILDONLY`, a committed set of placeholder values that lets them run without a real `.env`.

## Layout

| Path | |
| --- | --- |
| `src/pages/` | Routes. `src/pages/partials/*_component.astro` are the htmx partials |
| `src/components/` | `blocks/`, `compositions/` (layout primitives), `page/`, `partials/`, `layout/`, `icons/`, `logos/` |
| `src/helpers/` | API clients (`api.minmatar.org/`, `api.eveonline/`), i18n, gates, formatting |
| `src/json/feature_gates.json` | Access gates; see [frontend-feature-gating.md](../../docs/auth/frontend-feature-gating.md) |
| `src/styles/properties/` | Design tokens (colors, space, type, z-index) |
| `testing/` | vitest suites |
