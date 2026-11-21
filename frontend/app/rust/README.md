# Rust

Rust is the Minmatar Fleet component library: a [Storybook](https://storybook.js.org/) of the shared Astro
components in `src/components/`, deployed at **https://my.minmatar.org/rust/** and linked from the brand page
(`/brand/`).

It uses [`@storybook-astro/framework`](https://storybook-astro.org) in **server render mode**: the Storybook UI is
static, and each story's HTML comes from a small render server that renders the real `.astro` component with
Astro's Container API. Controls therefore re-render real components in production, not screenshots.

## Commands (from `frontend/app/`)

| Command | What it does |
| --- | --- |
| `npm run rust` | Storybook dev server on http://localhost:6006 |
| `npm run rust:build` | Builds `storybook-static/` (the UI) and `storybook-server/` (the render server) |
| `npm run rust:serve` | Serves the build at http://localhost:6007/rust/, as production does |
| `npm run rust:serve-local` | The same, also serving `public/` (images, fonts, site scripts), for when the website isn't running |
| `npm run rust:test` | Every story as a vitest case (also part of `npm run test`) |
| `npm run rust:test-browser` | Every story in Chromium against a running `rust:serve-local`: render, `play()`, page errors; axe results reported (`--a11y-strict` fails on them) |

## Layout

| Path | |
| --- | --- |
| `library.ts` | The inventory of shared components, by category. `testing/rust/library.test.ts` requires a stories file for each, with at least 3 stories, `play()` tests and a docs description |
| `stories/<category path>/*.stories.ts` | One stories file per component: `foundations/`, `layout/`, `components/<purpose>/`, `eve/` (and `eve/sde/`), `page/` |
| `foundations/tokens.ts` | Reads tokens, fonts, theme modes and hand-written colours from the source for the Foundations pages |
| `public/tokens.json` | Every root token in the Design Tokens Community Group format, served at `/rust/tokens.json` (`testing/rust/foundations.test.ts` keeps it current; `UPDATE_TOKENS=1` rewrites it) |
| `link_snapshot.mjs` | Post-build: points the render server's project snapshot at the app |
| `stories/_controls.ts` | Shared controls (token option lists), demo content, real EVE ids |
| `components/` | Story-only Astro helpers (icon and logo galleries) |
| `docs/*.mdx` | Introduction, tokens, writing stories |
| `server.mjs` | Production server: static UI + `/rust/render-api` (render server, allowlisted to the built components) + `/rust/health` |
| `healthcheck.mjs` | Container healthcheck (drain-aware, like `frontend/healthcheck.mjs`) |
| `browser_test.mjs` | The browser test runner |
| `../.storybook/` | Storybook config: the site's head scripts (Alpine, htmx, tippy), global styles, theme, htmx mocks |
| `../testing/rust/` | Vitest harness: renders each story with the Container API and runs its `play()` with Alpine in happy-dom |

## Production

`docker-compose-prod.yml` runs the `rust` target of `frontend/Dockerfile` as the `rust` service. `edge` (Traefik)
routes `/rust` and `/rust/*` to it; everything else on the website entry point stays on `frontend`. It rolls out
with zero downtime like `app` and `frontend` (`scripts/deploy.sh`, `docs/architecture/deploys.md`).

How it is organised (tokens → Layout → Components → EVE → Page) and why: `docs/Architecture.mdx`. See `docs/WritingStories.mdx` (or **Rust › Writing stories** in Storybook) for how to write stories.
