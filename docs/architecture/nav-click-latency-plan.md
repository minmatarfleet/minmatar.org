# Faster nav clicks: one-session runbook

Status: steps 1–6 built (Nov 2026, against `origin/main` at `5a5b433d7`, #3032); step 7 dropped, see below. The measured results are at the end.
Output: one branch and one PR, with **one commit per step**. Each commit stands on its own and can be reverted with `git revert` without touching the others.

## Why a click feels slow

The site navigates with Astro's `ClientRouter`, and prefetch is off. After a click, the old page stays on screen with `.loader` spinning until the server has run every `await` in the new page. **The wait is the destination page's server render time.**

A skeleton only helps when the page returns its shell first and fetches the data afterwards through a `LazyPartial`.

Every page also calls `get_gates` (`Viewport.astro`), which hits `GET /api/users/me/gates` with no cache, and every htmx partial calls it again in its own request. **Gates must be cached before any blocking section becomes a partial,** or the partials add backend load.

### Nav on `main` (after #3032)

| Nav item | Blocking work today | This session |
|---|---|---|
| Home `/` | `fetch_posts` (3 posts) | 60 s cache (step 6) |
| Fleets `/fleets/upcoming/` | fleet schedule: about 6 serial rounds; audiences fetched for everyone | parallel calls (step 3) + skeleton (step 5) |
| Corporation (leaders only) | slug, then info, then 3 independent calls in series | parallel calls (step 3) |
| Alliance, Ships, Market, Industry | gates only | gates cache (step 2); hover prefetch (step 7) was dropped |
| Learning `/learning/` | 6 serial rounds | parallel calls (step 3) |
| Fleets hub tab → Campaigns | `get_campaigns` | skeleton (step 4) |
| Fleets hub tab → History | `fetch_fleet_history`, which uses the same helper as the schedule | parallel calls come free with step 3 |

Fleets hub tab → Commanders makes a single call and is not in scope. Neither are the second-click pages (tribes, fittings, orders, doctrines, products): they get their own pass once this session's timing log exists.

## Decisions (defaults used unless you say otherwise)

| # | Decision | Default |
|---|---|---|
| D1 | While a fleet is live, the Fleets cover starts as the default image and cross-fades to the live location's cover once the list has loaded. The page can't know which fleet is live without the slow call. | **Accept.** It reuses the existing `/partials/fleet_cover` cross-fade. |
| D2 | The website may show a pilot's gates up to 60 s after a permission change. The backend still checks permissions on every API call. | **Accept, TTL 60 s.** `GATES_CACHE_TTL_SECONDS=0` turns it off. |
| D3 | Shape of the change | **One PR, one commit per step.** The alternative is stacked PRs per step, which take longer to review and merge. |
| D4 | Prod timings for logged-in pages need a prod `auth_token` cookie for read-only GETs. | **Public pages only** (anonymous `curl`), unless you provide a cookie. |

## What counts as a regression

Each step is checked against these rules before it is committed. The checks run for four personas (anonymous, member, superuser/FC, corp CEO) and for both a full page load and a soft navigation.

1. **Same content once loaded.** The settled `#content` DOM matches `origin/main`, with timestamps and "updated … ago" text normalized. D1 is the only allowed difference.
2. **Same access.** Status codes and redirect targets (200, 302 to login, 403, 404) are unchanged.
3. **One fetch per partial.** Each partial is requested once per view, and the Fleets 240 s refresh still fires once per interval.
4. **No more backend calls on the success path.** API calls per navigation are no higher than on `main`, gates included, counted from the timing log. A failure path may start an independent call that `main` would have skipped. That is listed per step.
5. **Same errors.** A failure renders the same fallback or `ErrorRefetch`, and the retry URL keeps the query parameters.
6. **Same query parameters.** `?host=` on Fleets and History, and `?persona=` and `?unavailable=1` on Learning, behave as before.
7. **SEO kept.** For anonymous visitors, `/` and `/learning/` keep their content and JSON-LD in the first HTML.
8. **No layout jump.** Each skeleton matches the outer size of the loaded block.
9. **Tests pass:** `npm run check` and `npm run test`.

## Setup (about 20 min)

Leave the other sessions' servers alone. That means :4321 (the user's dev server), :4323 and :8002 (another session's isolated stack), and the shared stash. Kill only PIDs this session started. The checks only send GETs, so both servers below use the existing :8000 backend.

```bash
cd /root/minmatar.org && git fetch origin
git worktree add -b perf/nav-click-latency ../minmatar.org-worktrees/nav-latency origin/main
git worktree add --detach ../minmatar.org-worktrees/nav-latency-base origin/main
```

- In both worktrees, run `npm ci` in `frontend/app` (not a symlinked `node_modules`), copy `frontend/app/.env`, and set `SDE_PATH=/root/minmatar.org/frontend/app/src/data/sde-3316380.sqlite`.
- Start the base with `astro dev --port 4325` and the branch with `astro dev --port 4326`. Record both PIDs.
- Personas: mint JWTs with the backend's `.env` `SECRET_KEY` (see the dev-auth recipe).
  - user 1: superuser and FC
  - one member: a user with `fleets.view` and no admin rights, found with a dev-DB query
  - one CEO: a user whose gates response has a non-empty `led_corporations`
  - anonymous: no cookie
  - If user 1 has no `DiscordUser` row, add the temporary dev row described in the recipe and delete it at the end.
- Scratchpad harness (`<scratchpad>/navperf/`). It is not committed, because Playwright is not a frontend dependency. Three scripts:
  - `ssr_diff.mjs`: GETs every target page as every persona on :4325 and :4326 with `API_TIMING_LOG=1`, normalizes CSRF tokens, timestamps, `data-astro-cid` hashes and the build hashes in asset URLs, then diffs the HTML and status codes.
  - `settled_dom_diff.mjs`: loads each page, both fully and via soft navigation (`window.navigate`, without awaiting it), waits until nothing is `aria-busy` and the network is idle, then diffs the normalized `#content`. It also counts requests per `/partials/*` URL.
  - `nav_timing.mjs`: from a fixed page, clicks each Neocom item five times and records the median time from click to `astro:after-swap` and to all-loaded.

Timing numbers come from **built** servers (`astro build` and `node dist/server/entry.mjs`), not `astro dev`. Build the base once at setup and the branch once at the end.

## Steps

### Step 1: API timing log (no behavior change)

- `helpers/api.minmatar.org/client.ts`: when a request store exists, record `{ endpoint path with ids replaced by :id, start, ms, status }` for each `api_request` and `api_response` call.
- `middleware.ts`: when `API_TIMING_LOG=1`, run `next()` inside an `AsyncLocalStorage` store. Wrap the response body in a `TransformStream` whose `flush` logs one line per request:
  `[api-timing] GET /fleets/upcoming/ calls=9 rounds=3 api_ms=412 render_ms=530 :: …`
  Rounds are counted from overlapping start and end times. The log runs at stream end because gates and other layout calls run after the headers are sent, so a `Server-Timing` header would miss them.
- When the flag is off there is no store, and recording is skipped with a single `if`.
- Tests: `testing/helpers/api_timing.test.ts`:
  - nothing is recorded without a store
  - inside a store, calls and rounds are counted (two concurrent calls make one round, two sequential calls make two)

**Gate:** `ssr_diff` shows identical HTML for every page and persona.
**Record:** baseline `calls` and `rounds` from :4325 and the built-server timings in the table at the end.

### Step 2: gates cache

- `helpers/gates.ts`: `load_gates` reads through a cache:
  - module-level `Map`
  - key: sha256 of the token
  - value: `{ gates, expires }`, with LRU eviction at 5,000 entries
  - concurrent misses share one in-flight promise
- Only successful responses are cached. A failure keeps today's fallback to an empty gate context, uncached.
- TTL comes from `GATES_CACHE_TTL_SECONDS` (default 60). It defaults to 0 when `process.env.VITEST` is set, so existing tests that reuse one token with different mocked gates don't leak into each other. Export `clear_gates_cache()` and `set_gates_cache_ttl()` for tests.
- Docs: add a "Caching" paragraph to `docs/auth/frontend-feature-gating.md` covering TTL, staleness and how to turn it off.
- Tests: `testing/helpers/gates_cache.test.ts`. Within the TTL, one fetch is shared. After the TTL, a new fetch happens. Failures are not cached. TTL 0 always fetches. Two concurrent calls make one fetch. A different token is a miss.

**Gate:**
- `ssr_diff` shows identical HTML and status codes.
- Timing log: from the second view on, each page has one call fewer, and each partial on a page has one call fewer.
- `testing/helpers/gates.test.ts` still passes unchanged.

### Step 3: parallel independent calls (no visible change)

Only the order and overlap of calls change. Each result is unwrapped in the same way as its old `try`/`catch`. Call `get_gates(Astro)` early in a page wherever the page needs gates anyway: it is memoized per request, so the layout reuses the same promise.

**`helpers/fetching/fleets.ts` `fetch_fleets_auth`:**
- Accept `fc_metrics` as an array, a promise or null.
- Start `get_fleets_v3` and `get_fleets_metrics` together, and await `fc_metrics` last.
- Failure path: if `get_fleets_v3` throws, `get_fleets_metrics` has already started, which `main` would have skipped.

**`helpers/fetching/fleet_schedule.ts`:**
- `fetch_fleet_schedule`: pass the `get_fleet_commander_metrics(...)` promise into `fetch_fleets_auth` (round 1). Once the filtered list is known (plus the group-id round when `?host=mine`), run `fetch_doctrine_names` alongside the `next` signups pair.
  - Before: 5 rounds, 6 with `mine`. After: 2 rounds, 3 with `mine`.
- `fetch_fleet_history`: same treatment, so History gets faster too.

**`pages/fleets/upcoming.astro`:**
- Call `get_audiences` only when `can_add_fleets` is true (`FlashFormButton` only renders then), and run it alongside the schedule.

**`pages/learning/index.astro`:**
- Round 1: `me`, `recommendation`, `get_gates` and `get_primary_characters`.
- Round 2: `get_characters_summary_sorted` (if gated), `get_skillsets` (if there is a primary character) and `get_learning_certificates`. Certificates need the persona, which needs `me` from round 1.
- Keep `main`'s semantics:
  - if `me` or `recommendation` throws, readiness, the admin links and skillsets stay empty
  - a skillsets or primary-character failure only empties skillsets
  - certificates get their own error flag
- Failure path: `get_primary_characters` has already started even when `me` fails.
- Before: 6 rounds. After: 2.

**`pages/alliance/corporations/[corporation]/index.astro`:**
- After `get_corporation_info`, run `get_user_corporation_id`, `get_corporation_list_by_id_auth` and `get_corporation_member_access` together. Each keeps its own `.catch`, and the 404 path makes no extra calls.
- Before: 5 rounds. After: 3.

Tests, using `testing/pages/*` with `AstroContainer` and `vi.mock` as in `corporation_projects_component.test.ts`:
- `testing/helpers/fleet_schedule_parallel.test.ts`:
  - the v3 and metrics calls start before fc_metrics resolves
  - with `?host=mine`, doctrines are fetched for the filtered fleets only
  - every call is made exactly once
- `testing/pages/learning_index_parallel.test.ts`: inject a failure into each call in turn, and check the rendered fallback matches what `main`'s code produces.
- `testing/helpers/parallel_fetching.test.ts`: the corporation and application calls start together; an applications failure, an open-application failure, and a corporation failure behave as before.

**Gate:**
- `ssr_diff` shows identical HTML and status codes for all personas, including Fleets with `?host=all|alliance|tribe|mine`, History, and Learning with `?persona=` and `?unavailable=1`.
- Timing log: `calls` are the same or lower, and `rounds` drop as listed.

### Step 4: Campaigns list behind a skeleton

- `pages/campaigns/index.astro`: drop `get_campaigns` and render
  `<LazyPartial url={CAMPAIGNS_PARTIAL_URL}><CampaignListSkeleton /></LazyPartial>`.
  - The shell keeps the login redirect, the `campaigns.view` 403, the cover, `FleetsHubTabs`, and the new and event-code buttons.
  - Keep `CampaignList` rendered somewhere on the page (for example an empty hidden instance) only if the partial route's manifest styles turn out not to include it. Check `dist/server/manifest_*.mjs` after the build. `htmx_partial_styles` (#2897) should already cover it.
- New `components/blocks/CampaignListSkeleton.astro`: same grid as `CampaignList`, fill from `@include skeleton.shimmer`, no keyframes.
- `campaign_list_component` already renders `ErrorRefetch`, so it doesn't change.
- Test: `testing/pages/campaigns_lazy_list.test.ts` checks that the shell makes no `get_campaigns` call and includes the LazyPartial URL.

**Gate:**
- `settled_dom_diff` matches.
- The partial is requested once on full load and on soft navigation.
- 403 and login-redirect statuses are unchanged.
- A 500 forced through a mock backend route shows `ErrorRefetch`.

### Step 5: Fleets list behind a skeleton

- `pages/fleets/upcoming.astro`:
  - Remove the schedule fetch. The shell keeps login, the `fleets.view` 403, `can_add_fleets`, audiences, and reading and deleting the `flash_form_error` cookie.
  - The cover becomes the static default (`/images/fleets-cover.jpg`, left-aligned).
  - `x-data` gets `fleets_count: 0`. No markup on the page reads it, and the 240 s refresh sets it.
  - Inside the unchanged `UpcomingFleetsUpdater`, render
    `<LazyPartial url="/partials/upcoming_fleets_initial_component/?host=<current>" swap="outerHTML"><FleetScheduleSkeleton /></LazyPartial>`.
  - The updater's 240 s poll replaces the slot's contents as before. Its timer starts at page load, also as before.
- New `pages/partials/upcoming_fleets_initial_component.astro`, the first load:
  - Renders `<FleetSchedule>` exactly as the page used to render it inline, without the refresh partial's "updated just now" label.
  - When `schedule.live[0]` has a location cover, adds a hidden trigger:
    `<div hx-get="/partials/fleet_cover?location_name=…" hx-trigger="load" hx-target="#viewport-cover-oob" hx-swap="outerHTML transition:true">`.
  - `fleet_cover` returns 400 (no swap) when the cover is unchanged, and makes no backend API call. This is decision D1.
  - On failure, renders `ErrorRefetch` with the retry URL keeping `host`.
  - This started as an `initial=1` mode inside `upcoming_fleets_component`. Wrapping that partial's template in one top-level expression moved Astro's injected `<style>` tags inside the refresh markup, so the first load got its own file. The refresh partial is byte-for-byte unchanged.
- Fix the existing bug in `fleet_list_component.astro`: the upcoming list ignored `?host=` and its `ErrorRefetch` URL dropped it. Pass it through.
- New `components/blocks/FleetScheduleSkeleton.astro`: a spotlight card, the type chips and two day rows at `FleetSchedule`'s sizes, stacked on phones, using `skeleton.shimmer`.
- Tests (`testing/pages/fleets_lazy_schedule.test.ts`):
  - the shell makes no schedule calls and passes `host` to the partial
  - the first load: no refresh label; a live fleet gives a `fleet_cover` trigger with the right location; no live fleet gives no trigger; an error gives `ErrorRefetch`
  - the refresh partial is unchanged
  - `fleet_list_component` filters by `host`

**Gate:**
- `settled_dom_diff` matches apart from D1, checked with no live fleet, one live fleet (temporarily set a dev fleet live, then restore it) and each `?host=` value.
- Exactly one initial partial request. A fake-clock run shows the poll at 240 s and 480 s.
- The flash-form alert still shows once.

### Step 6: home page posts cache

- `pages/index.astro`: route `fetch_posts({ page_num: 1, page_size: 3, status: 'published' })` through a small `helpers/memo_cache.ts` (`cached(key, ttl_ms, fn)`, sharing in-flight calls, never caching failures).
  - TTL from `HOME_POSTS_CACHE_TTL_SECONDS`, default 60; 0 under VITEST.
  - Step 2's gates cache uses the same helper.
- Tests: `testing/helpers/memo_cache.test.ts`.

**Gate:** `ssr_diff` shows identical HTML for anonymous visitors and members. A failure renders the existing error state.

### Step 7: hover prefetch for side-effect-free landing pages (dropped)

The plan was to turn on Astro's `prefetch` (`prefetchAll: false, defaultStrategy: 'hover'`) and add `data-astro-prefetch="hover"` to the Home, Alliance, Ships, Market and Industry Neocom buttons, with a conventions rule limiting it to those five.

It was built and measured, then dropped because it failed its gate:

- With the `ClientRouter`, Astro prefetches with `<link rel="prefetch">`, but the navigation then loads the page again with `fetch()`.
- These pages send no cache headers, so the browser does not reuse the prefetched response. The dev server rendered `/alliance/` twice for one hover and click.
- So prefetch doubled the server work and saved nothing.

Making the pages cacheable (`Cache-Control: private, max-age`) would let a pilot see a cached signed-in page after logging out, so that is not an option.

The workable route is a small `astro:before-preparation` handler that fetches on hover and hands the response to the router through `event.loader`. That means copying the router's default loader: redirect handling, the view-transitions meta check, `noscript` stripping and stylesheet preloading. It would also need its own reuse window. It is a follow-up, not part of this change.

After step 2, the five landing pages make no backend calls for a returning pilot, so the remaining gain is small.

**Never prefetch these, if this is revisited:**
- `/fleets/upcoming/`: its GET clears `flash_form_error`.
- Learning, Campaigns and corporation pages: every hover would cost a full backend round.

## Wrap-up (about 30 min)

1. Run `npm run check` and `npm run test` in `frontend/app` on the branch. No backend changes are planned. If one creeps in, run the backend suite too.
2. Build the branch and run `nav_timing.mjs` on the built base and branch servers. Fill in the table below.
3. Prod baseline for public pages (Home, Alliance, Ships, Market, Industry, anonymous Learning): five `curl -w '%{time_starttransfer}'` samples each, GET only, plus logged-in pages if a cookie was provided (D4).
4. Copy this doc into the branch and commit it with step 1.
5. Open the PR. List the steps as commits, and paste the `ssr_diff` and `settled_dom_diff` summaries, the timing table, D1/D2, and a rollback line per step:
   - steps 2 and 6: environment TTL = 0
   - other steps: `git revert`
6. Clean up: stop PIDs 4325 and 4326, delete the base worktree, and remove the temporary `DiscordUser` row if it was added.

**If a step fails its gate and the fix isn't obvious within about 20 minutes,** drop that commit and ship the rest. The steps are independent apart from these dependencies:

- 4 and 5 need 2
- 5 needs 3's audiences change, which is easy to carry over

## Results

Measured on 2026-11-06 with production builds (`astro build`, then `node dist/server/entry.mjs`) of `origin/main` and this branch. Both used the same local backend and a clone of the dev DB with one live and three upcoming fleets, signed in as a superuser.

- **Calls / rounds** come from the `API_TIMING_LOG` line for the page itself. For the two lazy pages, the partial's calls are shown after the `+`.
- **Swap**: time from the click (a ClientRouter navigation from `/ships/`) to `astro:after-swap`, which is when the new page appears.
- **Loaded**: time until nothing is `aria-busy` and no htmx request is in flight.
- Times are the median of 5 runs, after one warm-up run.

| Nav item | main calls / rounds | branch calls / rounds | main swap → loaded | branch swap → loaded |
|---|---|---|---|---|
| Home | 4 / 4 | 1 / 1 | 354 → 413 ms | 176 → 235 ms |
| Fleets | 13 / 7 | 1 / 1 + 11 / 2 | 521 → 577 ms | 147 → 313 ms |
| Fleets → Campaigns tab | 2 / 2 | 0 / 0 + 1 / 1 | 289 → 358 ms | 132 → 251 ms |
| Fleets → History tab | 4 / 4 | 3 / 1 | 259 → 315 ms | 156 → 209 ms |
| Corporation | 8 / 8 | 7 / 3 | 562 → 623 ms | 290 → 342 ms |
| Alliance | 1 / 1 | 0 / 0 | 128 → 185 ms | 96 → 152 ms |
| Ships | 1 / 1 | 0 / 0 | 131 → 190 ms | 83 → 142 ms |
| Learning | 12 / 8 | 11 / 3 | 532 → 592 ms | 364 → 418 ms |
| Market | 1 / 1 | 0 / 0 | 124 → 180 ms | 90 → 149 ms |
| Industry | 1 / 1 | 0 / 0 | 123 → 182 ms | 101 → 157 ms |

Local backend calls take 20–80 ms. In production, each removed sequential round also saves a network round trip, so the gain there should be larger. Prod time to first byte for anonymous pages was measured from the dev machine: about 220 ms of server time after TLS for every public page, including ones with no backend calls, so most of it is round trip. Logged-in prod pages were not measured (decision D4).

### Parity checks

All of these compared `main` against the branch:

- **SSR diff:** 19 pages and partials × 5 personas (anonymous, member, FC, superuser, corp CEO).
  - After steps 1, 2, 3 and 6, the HTML and status codes are identical everywhere.
  - Steps 4 and 5 change the shells of `/campaigns/` and `/fleets/upcoming/` by design.
- **Settled-DOM diff:** full load and soft navigation, superuser and member.
  - Campaigns, Learning, Home and Fleets with `?host=tribe` or `?host=mine` are identical after loading.
  - Fleets with a live fleet differs only in a whitespace text node in the cover and in the refresh poller's fallback `X-Page-Cover` value. That value is only used when `sessionStorage` has no cover, and the swapped-in cover sets it.
- **Requests:** each lazy partial is requested once per view.
- **Fleets refresh:** with a fake clock, one request at +240 s and one at +480 s, the same as `main`.
- **Flash-form alert:** shown once, the cookie is cleared, and the alert is gone after a reload, the same as `main`.
- **Production build:** the lazy partial routes carry their components' CSS, and the loaded pages look the same as `main`.
