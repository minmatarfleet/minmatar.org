---
name: amamake-market-report
description: >-
  Produce the monthly Amamake Market Report at /amamake-market/ (my.minmatar.org
  frontend). Use when asked to build, publish, refresh, or add a new month's
  Amamake market report / freeport report / "what sold in Amamake", or to update
  its sales, died-vs-sold, catchment, or industry data. One cached extraction
  pass (site API + the Warzone Report's zKillboard cache) feeds a data-driven
  Astro component reused every month.
---

# Amamake Market Report (monthly)

A public monthly report on the Amamake freeport market, at `/amamake-market/`
(latest) and `/amamake-market/<slug>/`. It is the market twin of the Warzone Report
and follows the same shape: **one extractor writes a generated data file, one hand
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
   edit — re-run). `<slug>.ts` is the editorial layer: the opening, deks, the Focus
   story, and the two manual tables (import vs local, LP conversion). Interpolate
   generated numbers into prose (template strings) instead of typing them, so a
   regenerated extract never leaves stale figures in the text.

## Data sources

| Data | Source |
|------|--------|
| Inferred fills (ISK, units, fills, per day, per type) | my.minmatar.org API `inferred-sales/monthly` (order-book diffs, ~15 min snapshots) |
| Ships / ISK destroyed per FW system, hulls lost in Amamake, characters on mails | zKillboard `kills/systemID/<id>/year/<y>/month/<m>/` via the shared cache |
| FW system list + current holder | ESI `GET /fw/systems/` |
| System cost indices (manufacturing, reaction) | ESI `GET /industry/systems/` — a **live snapshot**, dated in the output |
| Hub health (sell-order / contract health %, ISK on the book) | my.minmatar.org API `market/health` — live snapshot, nullable |
| Type names, categories, capital classification, system → region | local SDE sqlite `src/data/sde-*.sqlite` (no API) |
| Jita prices, freight, LP store math | **manual** — hand-authored tables in the issue file (like Dotlan occupancy in the warzone report) |

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
   `CATEGORIES`, `TOP_TYPES`, `HULLS` (+ `HULLS_SOLD_TOTAL`/`HULLS_LOST_TOTAL`),
   `AMAMAKE`, `WARZONE`, `CATCHMENT`, `REGIONS`, `PIPE`, `CAPITAL_SPLIT`,
   `INDUSTRY_INDICES` (+ `INDUSTRY_AS_OF`), `HUB_HEALTH`, `EXTRACTED_AT`.
   If the warzone issue for the month has not been generated yet, the kill pass fetches
   ~70 systems × 2 months from zKillboard (10–20 min, rate-limited) and caches them for
   the warzone report too.

2. **Author the issue file** `src/data/amamake-market/yc128-09.ts`: copy the previous
   month's `.ts`, change the imports to `./yc128-09-boards`, update `SLUG`,
   `published_at` (last day of the month), `period_utc`, `previous_period_label`,
   `context_as_of`. Rewrite the editorial fields: `headline`, `opening`, section deks
   and footnotes, the `focus` story (title, dek, closing, CTA — pick the month's story),
   the `import_vs_local` and `loyalty` tables (month-end Jita/Amamake prices and LP
   store rates — the only manual inputs), and `shelf`/`get_involved` if anything moved.
   Keep every number that exists in the boards file interpolated, not typed.

3. **Register the issue:** add it to `ISSUES` in `src/data/amamake-market/index.ts`
   (latest sorts first automatically) and add a `kind: 'market'` entry to the
   content-hub list in `src/data/campaigns/index.ts` (`iskDestroyed: <ISSUE>.sales.isk`,
   `isk_label_key: 'sold'`).

4. **i18n + sitemap:** add `amamake_market.<slug_with_underscores>.*` strings in
   `src/i18n/ui.ts` (name, page_title, period, leading_text, meta_title,
   meta_description) plus `page_finder.amamake_market.<slug>.description`, and one
   entry in `src/json/sitemap.json` (`/amamake-market/` already points at the latest).

5. **Verify** (see Verification). No route work is needed —
   `pages/amamake-market/[issue].astro` serves any registered slug.

## What each section shows

- **Hero**: four stat tiles — inferred ISK sold (▲/▼ % vs prior month), inferred fills,
  ships destroyed in Amamake, focus story. Then a jump nav (section chips).
- **The month**: editorial opening paragraphs.
- **Through the book**: a per-day ISK strip (one column per calendar day; hatched columns
  are days with no snapshots — visible gaps are a feature), a weekly table with bars,
  and a "where the ISK went" share bar by category (Ships / Modules / Charges / …).
- **What sold**: top types by inferred ISK with type icons, units × fills, MoM % and a
  NEW badge for types with no fills the prior month.
- **Died vs sold**: hulls lost in Amamake vs inferred sells of the same hull, side-by-side
  bars, MoM deltas, and a sold-per-loss ratio (green ≥ 1, red < 1).
- **The catchment**: region share bar, warzone/pipe/Amamake stat line, and a per-system
  table (holder mark, ships bar, vs prior month, ISK, capital share) — same numbers as the
  Warzone Report's "Where the ships died".
- **Focus of the month**: the curated story with stat tiles, a capital-vs-subcap stacked
  bar per system, and a CTA (internal path or external URL).
- **Import vs local**, **Loyalty points**: hand-authored tables (rows can carry a `tone`).
- **Build in Amamake**: ESI cost indices for the configured systems, dated.
- **The shelf**: hub-health stat tiles (when the API has them) plus outbound links.
- **Use the hub**: three step cards, a CTA, featured guides.
- **About the numbers**: methodology definition list + source chips.
- Bottom: previous / browse all / next report nav and a colophon.

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
