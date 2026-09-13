---
name: amamake-market-report
description: >-
  Produce the monthly Amamake Market Report at /amamake-market/ (my.minmatar.org
  frontend). Use when asked to build, publish, refresh, or add a new month's
  Amamake market report / freeport report / "what sold in Amamake", or to update
  its sales, died-vs-sold (Amamake sells vs warzone losses), catchment, or industry data. One cached extraction
  pass (site API + the Warzone Report's zKillboard cache) feeds a data-driven
  Astro component reused every month.
---

# Amamake Market Report (monthly)

A public monthly **Amamake Economic Report** on the Amamake freeport market, at `/amamake-market/`
(latest) and `/amamake-market/<slug>/`. It is one of two Warzone Reports (Frontline and
Amamake Economic) and follows the same shape: **one extractor writes a generated data file, one hand
authored issue file supplies the prose, one shared component renders every issue.**
A new month is: run one script, copy last month's issue file, rewrite the editorial
text, register it. Do not rebuild the UI each month.

Working dir for every command below: `frontend/app`.

## The golden rules

1. **Sales come from the site, not from a spreadsheet.** CCP does not publish
   structure transactions. The backend infers sell fills from successive Amamake
   order-book snapshots (`EveMarketInferredSale`). The extractor reads them through
   `GET /api/market/inferred-sales/monthly?location_id=1022167642188&year=&month=`
   for the target month and the prior month (deltas). Run it against **production**
   (`--api https://api.minmatar.org`, the default). The local dev database has gaps
   whenever the dev sync was down — its monthly totals are not publishable.
2. **Destruction shares the Warzone Report's zKillboard cache.** Per-system kill pages
   live in `.cache/warzone/systems/` with the same filenames `warzone_extract.mjs`
   uses, so if the warzone issue for the month has been generated, the market
   extractor makes **zero** zKillboard requests. Never write ad-hoc kill loops; never
   query zKillboard by region (it undercounts busy regions).
3. **The component is shared — reuse it, don't duplicate.** `AmamakeMarketReportIssue.astro`
   renders every section from an `AmamakeMarketIssue` object. A new month writes
   **data**, not markup. If a section needs a real change, change the one component.
4. **Generated vs hand-authored.** `<slug>-boards.ts` is machine-generated (never hand
   edit — re-run). `<slug>.ts` is the editorial layer: the opening and section deks.
   Interpolate generated
   numbers into prose (template strings) instead of typing them, so a regenerated
   extract never leaves stale figures in the text. There is no Focus section on
   the Amamake Economic report — Frontline warzone reports keep theirs.

## Data sources

| Data | Source |
|------|--------|
| Inferred fills (ISK, units, fills, per day, per type) | my.minmatar.org API `inferred-sales/monthly` (order-book diffs, ~15 min snapshots) |
| Ships / ISK destroyed per FW system, hulls lost in Amamake, characters on mails | zKillboard `kills/systemID/<id>/year/<y>/month/<m>/` via the shared cache |
| FW system list + current holder | ESI `GET /fw/systems/` |
| Hub health (sell-order / contract health %, ISK on the book) | my.minmatar.org API `market/health` — live snapshot, nullable |
| Finished contracts (ISK, count, hull) | `EveMarketContract` via production_readonly cache dump |
| Jita guide / worth-seeding spread / inferred profit | Forge `EveMarketItemHistory` via production_readonly + SDE packaged volume × alliance Jita→Amamake freight (450 ISK/m³, freight calculator `EveFreightRoute`) |
| Type names, categories, capital classification, system → region | local SDE sqlite `src/data/sde-*.sqlite`, then inferred-sales payload names, then ESI `POST /universe/names/` + `GET /universe/types/{id}/` (cached under `.cache/amamake-market/esi-types.json`) |
| Month-end import vs local snapshot | **not shown** — leftover issue data, not rendered |

Key ids and thresholds live in [config.json](./config.json).

## Publish a new month — checklist

Example: September YC128 → year 2026, month 9, slug `yc128-09`.

1. **Generate the data:**
   ```bash
   npm run amamake:extract -- --year 2026 --month 9 --slug yc128-09
   ```
   Options: `--api <base>` (default production; `http://localhost:8000` for dev),
   `--top 10` types, `--hulls 8`, `--systems 8`, `--caps 6`, `--exclude <type ids>`
   for editorial exclusions (one-buyer BPC fills, sellouts), `--pipe` to change the
   Heimatar pipe system list. Closed months are cached under `.cache/amamake-market/`;
   the running month is always refetched. Writes `src/data/amamake-market/yc128-09-boards.ts`
   exporting `SALES_TOTALS`, `SALES_TOTALS_PREV`, `SALES_TOTALS_VS`, `DAYS`, `WEEKS`,
   `CATEGORIES`, `TOP_TYPES`, `TOP_TYPES_BY_CLASS`, `HULLS` (+ `HULLS_SOLD_TOTAL`/`HULLS_LOST_TOTAL`),
   `AMAMAKE`, `WARZONE`, `CATCHMENT`, `REGIONS`, `PIPE`, `CAPITAL_SPLIT`,
   `CONTRACTS`, `CONTRACT_HULLS`, `MARGINS` (+ `JITA_AS_OF`, `FREIGHT_ISK_PER_M3`), `HUB_HEALTH`,
   `EXTRACTED_AT`. `SALES_TOTALS.profit` is (Amamake − Jita − freight/unit) × units over priced types.
   If the warzone issue for the month has not been generated yet, the kill pass fetches
   ~70 systems × 2 months from zKillboard (10–20 min, rate-limited) and caches them for
   the warzone report too.

2. **Author the issue file** `src/data/amamake-market/yc128-09.ts`: copy the previous
   month's `.ts`, change the imports to `./yc128-09-boards`, update `SLUG`,
   `published_at` (last day of the month), `period_utc`, `previous_period_label`,
   `context_as_of`. Rewrite the editorial fields: `headline`, `opening`, and section deks
   and footnotes on the briefing (The month, Market sales overview, What sold,
   Items worth seeding, Market Capture). Keep every number that exists in the boards
   file interpolated, not typed.
   The Amamake Economic report has no Focus, Build in Amamake, Loyalty points,
   Contracts, Import vs local, Shelf, Use the hub, or About the numbers sections.

3. **Register the issue:** add it to `ISSUES` in `src/data/amamake-market/index.ts`
   (latest sorts first automatically) and add a `kind: 'warzone'` /
   `warzone_type: 'economic'` entry to the content-hub list in
   `src/data/campaigns/index.ts` (`iskDestroyed: <ISSUE>.sales.isk`,
   `isk_label_key: 'sold'`). It appears on the shared **Warzone Reports** strip
   next to that month's Frontline report.

4. **i18n + sitemap:** add `amamake_market.<slug_with_underscores>.*` strings in
   `src/i18n/ui.ts` (name, page_title, period, leading_text, meta_title,
   meta_description) plus `page_finder.amamake_market.<slug>.description`, and one
   entry in `src/json/sitemap.json` (`/amamake-market/` already points at the latest).

5. **Verify** (see Verification). No route work is needed —
   `pages/amamake-market/[issue].astro` serves any registered slug.

## What each section shows

- **Hero**: three stat tiles — inferred ISK sold (▲/▼ % vs prior month), inferred profit
  (markup vs Jita minus Jita→Amamake freight, ▲/▼ ISK vs prior month),
  and ships destroyed at the hub (Amamake only — the shop fueling the warzone). No Focus tile.
- **The month**: editorial opening paragraphs.
- **Market sales overview**: a per-day ISK strip (one column per calendar day; hatched columns
  are days with no snapshots — visible gaps are a feature) and a sell-orders-by-class table
  (Ships / Rigs / Modules / Charges / …) with MoM ISK, fills, units, and volume-weighted
  average markup versus Jita.
- **What sold**: top types by inferred ISK with type icons, units × fills, MoM %, average
  markup versus Jita (em-dash when Jita is missing), and a
  NEW badge for types with no fills the prior month. Class chips (htmx) swap the
  list: All is the overall top ten; each class is that bucket's top ten.
  Classes come from `bucket_for_type` in the extractor: Ships / Rigs / Modules /
  Charges / Drones / **PLEX adjacent** (skill injectors, Skill Extractor, PLEX, MPT) /
  Implants / Materials (including harvested gas, fullerite, magmatic gas) / Other
  (blueprints fold here — no Blueprints chip).
- **Items worth seeding**: types whose inferred fill average beats Jita plus freight,
  with enough volume that another hauler can participate without cooking the book
  (25 inferred fills and 25 units — August 2026 participation floor; among
  5%-over-Jita types, median fills were 29 and the units quartile was 21).
  Ranked by extra ISK (spread × units), not fattest %. Blueprints excluded.
- **Market Capture**: inferred sells at Amamake vs hulls lost in the Amarr–Minmatar
  warzone (side-by-side bars, MoM deltas, sold-per-loss ratio) plus the catchment
  around the shop — region share bar, warzone/pipe/Amamake stat line, and a
  per-system table (holder mark, ships bar, vs prior month, ISK, capital share).
  Same kill numbers as the Warzone Report's "Where the ships died". One section,
  one jump-nav chip.
- Bottom: previous / browse all / next report nav and a colophon.

Do **not** re-author Focus of the month, Build in Amamake (cost indices), Loyalty
points, Contracts, Import vs local, The shelf, Use the hub, or About the numbers.

## Verification

```bash
export $(cat .env.BUILDONLY) && npx astro check --minimumSeverity error
export $(cat .env.BUILDONLY) && npx vitest run testing/components/blocks/AmamakeMarketReportIssue.test.ts testing/data/amamake-market.test.ts
```
Backend (from `backend/`, sqlite test settings):
```bash
set -a; . ./standalone.env; set +a; export SETUP_TEST_DATA= DJANGO_SETTINGS_MODULE=app.settings_test
python manage.py test market.tests.test_inferred_sales_monthly
```
Then preview `http://localhost:4321/amamake-market/`. For screenshots use the Playwright
approach in the memory note `reference-playwright-screenshots`.

## Gotchas

- **Dev database ≠ production.** The dev sync stops whenever the dev stack is down, so
  monthly totals from `localhost:8000` are a floor of a floor. Use them to develop; publish
  from production. The boards header records which API produced it.
- The monthly endpoint caches closed months for 24h and the running month for 15 min.
- Ships destroyed exclude capsules and NPC-only kills (same rule as the warzone report),
  so counts are lower than zKillboard's raw system totals.
- Single-fill hulls and blueprint copies can top the ISK board on one buyer; drop them with
  `--exclude` and say so in the footnote, or wait for a second month.
- Hub health percentages are `null` when the API has no targets configured; the shelf
  tiles skip them automatically.
- Keep `.cache/warzone/` and `.cache/amamake-market/` between runs; deleting them forces a
  full re-fetch.
- The bundled SDE (`src/data/sde-*.sqlite`) lags CCP patches. The extractor fills missing
  type names from the sales payload, then ESI, so a new hull or SKIN never publishes as
  `Type {id}`. Refreshing the sqlite still helps volume/capital classification.
