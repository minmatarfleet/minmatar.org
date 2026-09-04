---
name: warzone-report
description: >-
  Produce the monthly Amarr–Minmatar Warzone Report at /warzone/ (my.minmatar.org
  frontend). Use when asked to build, publish, refresh, or add a new month's
  warzone report / warzone recap / FW monthly report, or to update its pilots,
  groups, scoreboard, traffic, or occupancy data. One cached zKillboard pass
  feeds a data-driven Astro component reused every month.
---

# Warzone Report (monthly)

A public, siege-style monthly report on the Amarr–Minmatar faction-warfare zone, at
`/warzone/` (latest) and `/warzone/<slug>/`. All numbers come from public APIs; a
single generated data file feeds one shared, data-driven component. **A new month is
almost entirely: run one script, copy last month's issue file, edit the editorial
prose, register it.** Do not rebuild the UI each month.

Working dir for every command below: `frontend/app`.

## The golden rules

1. **One cached zKillboard pass. Never hammer it.** The whole report is built by
   `scripts/warzone_extract.mjs`, which fetches each warzone system **once** and
   caches every page under `frontend/app/.cache/warzone/` (git-ignored). Re-runs and
   design iteration cost **zero** new requests. The script sleeps ~1.1s between live
   fetches and backs off on 429/5xx. Never write ad-hoc per-kill or per-region loops.
2. **Query per-system, not per-region.** zKillboard's `regionID` kills API is capped
   (~10k) and silently undercounts busy regions — it missed ~30% of Amamake. The
   authoritative source is the ~70 per-system killboards (system list from ESI). This
   is already how the script works; don't "optimize" back to regions.
3. **The component is shared — reuse it, don't duplicate.** `WarzoneReportIssue.astro`
   renders every section from an issue object. A new month writes **data**, not markup.
   If a section needs a real change, change the one component (it affects all issues).
4. **Generated vs hand-authored.** `<slug>-boards.ts` is machine-generated (never hand
   edit — re-run). `<slug>.ts` is the editorial layer: prose, the occupancy flip
   narrative, and the Focus story, wired to the generated numbers.

## Data sources (all public)

| Data | Source |
|------|--------|
| Warzone system list + current holder | ESI `GET /fw/systems/` (owner faction 500002/500003) |
| Systems held, enlisted pilots, VP | ESI `GET /fw/stats/` |
| Per-system ships & ISK destroyed, pilots, groups, deltas | zKillboard `kills/systemID/<id>/year/<y>/month/<m>/` |
| Group warzone-share denominator | zKillboard `kills/<alliance|corporation>ID/<id>/…` |
| Character / alliance / corp names | ESI `POST /universe/names/` |
| System → region / constellation | local SDE sqlite `src/data/sde-*.sqlite` (no API) |
| Faction / alliance / corp logos | `images.evetech.net` (no faction endpoint — use faction NPC-corp logo) |

Key ids and thresholds live in [config.json](./config.json).

## Publish a new month — checklist

Example: August YC128 → year 2026, month 8, slug `yc128-08`.

1. **Generate the data (the only zKillboard step):**
   ```bash
   npm run warzone:extract -- --year 2026 --month 8 --slug yc128-08 --traffic 12
   ```
   First run fetches the two months (~10–20 min, rate-limited); it prints progress to
   stderr and writes `src/data/warzone/yc128-08-boards.ts`. Re-runs are instant from
   cache. The file exports: `SCOREBOARD_STATS`, `BOARDS_SAMPLED_KILLS`,
   `BOARDS_TOTAL_ISK`, six pilot boards (`MINMATAR_*` / `AMARR_*`), three ship boards
   (`SHIPS_SOLO` / `SHIPS_SMALL_GANG` / `SHIPS_FLEET`), `GROUPS`, `TRAFFIC`,
   `FRONTS`, `SYSTEM_STATS`.

2. **Author the issue file** `src/data/warzone/yc128-08.ts`: copy the previous month's
   `.ts` as a template and change the imports to `./yc128-08-boards`. Wire the
   generated exports through (scoreboard, sampled totals, traffic, fronts, occupancy
   numbers via the `system_stat()` helper). Write/refresh the editorial fields:
   `opening`, `occupancy` flip list (dates, `taken_by`, notes — from Dotlan system
   history, the one non-API input), and the `focus` story. Update `published_at`,
   `period_utc`, `esi_as_of`, and `previous_period_label`.

3. **Register the issue:** add it to `ISSUES` in `src/data/warzone/index.ts`
   (latest sorts first automatically) and to the content-hub list in
   `src/data/campaigns/index.ts`.

4. **i18n + sitemap:** add `warzone.<slug_with_underscores>.*` strings in
   `src/i18n/ui.ts` (name, page_title, period, leading_text, meta_title,
   meta_description) plus the `page_finder.warzone.<slug>.description`, and two
   entries in `src/json/sitemap.json` (latest already points at `/warzone/`).

5. **Custom alliance logos** (only for groups CCP/zKill has no logo for yet): see
   below. Skip entirely if every listed group resolves on the image server.

6. **Verify** (see Verification). No route work is needed — `pages/warzone/[issue].astro`
   already serves any registered slug.

## What each section shows (all data-driven)

- **Hero**: masthead + four stat tiles (systems flipped, ships destroyed, ISK, focus).
- **Scoreboard**: occupancy split bar (systems held) + number-label-number rows for
  Enlisted pilots (ESI total), Active pilots (unique militia pilots on a kill, zKill)
  and Kills (zKill). Faction values sit at the outer edges.
- **Systems**: an occupancy-changes table (When / System / Previous owner / New owner
  with faction emblems / Ships / vs prior month / ISK) and a "Where the ships died"
  table with per-system bars coloured by current holder. Deltas render as an aligned
  arrow+number, green up / red down.
- **Two fronts**: share bar + per-front cards.
- **Focus of the month**: the one curated deep-dive (currently the Auga siege, from
  `src/data/campaigns/auga.ts` — a separate hand-collected dataset shared with the
  `/campaigns/…` siege page; leave it unless writing a new focus).
- **Pilots of the month**: solo / small gang / fleets, both militias, with each
  pilot's alliance-or-corp affiliation.
- **Top ships**: most-destroyed hulls per engagement size (solo / small gang / fleets).
- **Groups of the month**: alliances (or player corps w/o alliance), NPC corps
  excluded, only groups with >50% of their monthly kills in-warzone, faction emblem +
  full faction name subtitle.
- **How to get involved**: three numbered step cards, a single "Join Militia Discord"
  CTA, and three featured guide cards + "Browse all guides".
- **About the numbers**: methodology + what public data can't show.

## Engagement buckets

Pilot boards split by attackers on the mail: **solo = 1, small gang = 2–24, fleet =
25+** (in `bucket_for` in the script). The Focus "how the week was fought" mix uses the
curated campaign dataset's own buckets — they can differ; that's expected.

## Custom alliance logos

Groups CCP/zKill has no logo for use a local override. The component checks
`public/images/warzone/logos/<slug>.png` and falls back to the CCP logo if absent.
To add one, background-remove the source and write it to that path:
```bash
python3 scripts/cutout_logo.py ~/Downloads/raw.png public/images/warzone/logos/<name>.png --trim
```
`cutout_logo.py` flood-fills transparency from the edges, so interior black is kept
(right for both emblem-on-black art and rounded-square app icons). Then map the
alliance id → path in `GROUP_LOGO_OVERRIDES` in `WarzoneReportIssue.astro`. Faction
subtitle logos use the empire SVG components (`MinmatarLogo`/`AmarrLogo`) or, for
pirate factions, the faction NPC-corp logo from the image server.

## Verification

```bash
export $(cat .env.BUILDONLY) && npx astro check --minimumSeverity error
export $(cat .env.BUILDONLY) && npx vitest run testing/components/blocks/WarzoneReportIssue.test.ts testing/data/warzone.test.ts
```
Then preview `http://localhost:4321/warzone/` (dev server usually already running on
4321). For screenshots use the Playwright approach in the memory note
`reference-playwright-screenshots`.

## Gotchas

- Never hand-edit `<slug>-boards.ts`; re-run the extractor.
- If a group shows the wrong side, the militia colour follows the pilots' **dominant
  faction** (pirates → null militia, shown neutral with the faction name).
- Empty pilot boards ("Not in this month's extract") mean the extract didn't run or
  the month is wrong — check the `--year/--month/--slug` args.
- Occupancy flip dates and the flip count are the only figures not from a public API
  (Dotlan). "Holds today" per system is ESI-live and may differ from `taken_by` when a
  system flipped back after the snapshot — reflect that in the note text.
- Keep the raw-page cache (`.cache/warzone/`) between runs; deleting it forces a full
  re-fetch.
