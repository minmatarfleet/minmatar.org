# Minmatar Fleet Academy Graduation

Identify L3ARN pilots ready to graduate, route them to alliance corps using **behavioral data** (Discord voice, fleet attendance, killmail gang sizes), and output a Google Sheets–ready TSV.

**The skill is the product.** `SKILL.md` holds graduation gates, routing judgment, and output format. `examples.md` stores learnings. `scripts/fetch_academy_pilots.py` only pulls metrics — it does not route.

## Quick start

```bash
cd backend
pipenv run python ../.cursor/skills/academy-graduation/scripts/fetch_academy_pilots.py --json
```

Requires `production_readonly` DB access (see `.cursor/skills/debug-production-readonly-db/SKILL.md`).

## What it does

1. Pull all pilots in Minmatar Fleet Academy (`L3ARN`, corp ID `98741376`)
2. Attach 90-day behavior: voice minutes, fleets, kills by gang size, SP, prime time
3. Agent applies graduation gate — exclude pilots who should stay
4. Suggest corp tickers (multi-corp OK) with short pilot summaries
5. Output markdown table + copy-paste TSV

## Corp tickers

| Ticker | Corp |
|--------|------|
| FOSFO | The Ministry Of Ungentlemanly Warfare (EUTZ skirmish) |
| TDT | The Dark Tribe (USTZ killers) |
| SLTAR | Soltech Armada (fleet/comms FW) |
| A-RAT | Rattini Tribe (all-TZ, scales up) |

FOSFO replaced Administrative Atrocities as the EUTZ graduate path. Verify corps against `api.minmatar.org` each run.

## Configuration

`config.json` — academy corp ID, behavior window, graduate days, corp ticker reference.

## Cursor usage

```
Run the academy graduation report
```

```
Pull L3ARN tenure and who should graduate
```

The agent follows `SKILL.md`, runs the fetch script, applies routing, and outputs TSV on request.
