---
name: town-hall-summary
description: Generate alliance town hall summaries from tribe catalog report bindings. Use when the user asks for town hall data, tribe slide metrics, town_hall_report output, production town hall analysis, or summaries by Capitals/Supply/Pulse groups.
---

# Town Hall Summary

Generate slide-ready summaries from **`town_hall_report`** and the report API. Metrics are keyed by **`TribeGroup.code`** (see `backend/tribes/reports/registry.py`).

## When to use

- User asks for town hall numbers, tribe summaries, or "what can we infer" for the last 30 days
- Preparing Capitals / Supply / Pulse slides
- Comparing production data without SSH (local + `production_readonly`)

Also read **`debug-production-readonly-db`** when querying prod from the dev machine.

## Run reports

From **`backend/`**, always use **`pipenv run`**.

### Full deck (automated groups only)

```bash
pipenv run python manage.py town_hall_report \
  --all --view town_hall --period 30d \
  --database production_readonly --format json
```

### Single group

```bash
pipenv run python manage.py town_hall_report \
  --group supply.mining --view town_hall --period 30d \
  --database production_readonly --format json
```

### Mining: tribe vs alliance

Default town hall binding for mining is **alliance**. For Mining **tribe roster** only:

```bash
pipenv run python manage.py town_hall_report \
  --group supply.mining --scope roster --view town_hall --period 30d \
  --database production_readonly
```

`--scope` accepts `roster` or `alliance` (not valid for program-scoped reports like freight).

### CSV (single group, tabular slides)

```bash
pipenv run python manage.py town_hall_report \
  --group supply.mining --format csv --period 30d \
  --database production_readonly
```

### API (on prod, chiefs only)

`GET /api/tribes/{tribe_id}/groups/{group_id}/reports/town_hall?period=30d&scope=roster`

## Automated vs manual groups

| Tribe | Code | Automated metric |
|-------|------|------------------|
| Capitals | `capitals.dreads`, `capitals.carriers`, `capitals.faxes` | Kills, losses, fleet ops (qualifying hulls); top 5 by kills |
| Supply | `supply.mining` | Volume m³ + ore ISK; top 5 (alliance default) |
| Supply | `supply.planetary-interaction` | Gross PI ISK; top 5 roster |
| Supply | `supply.capital-production`, `supply.subcapital-production` | Delivered/committed units + margin; top 5 by delivered margin |
| Supply | `supply.freighters` | Program totals only (contracts, ISK, m³, completion hours) |
| Pulse | `pulse.fleet-commanders` | Fleets led; top 5 alliance-wide |

**Manual (narrative only — no query data):**

- Supply: `supply.market`, `supply.loyalty-points`
- Pulse: `pulse.technology`, `pulse.thinkspeak`, `pulse.readiness`, `pulse.advocates`, `pulse.tournaments`

Manual groups return `manual: true` and a message; note them in **Slide readiness**, do not invent numbers.

## Scopes

| Scope | Meaning |
|-------|---------|
| `alliance` | All linked pilots in the data source |
| `roster` | Active tribe group members only |
| `program` | Alliance-wide program (freight); not overridable |

Town hall vs member view: bindings may differ (e.g. mining alliance vs roster). Check JSON `scope` field in output.

## Workflow

1. Run `--all` against `production_readonly` (or prod API if user is on prod).
2. For **mining**, also run with `--scope roster` if the slide should be tribe-focused.
3. Parse JSON: `period_start`, `period_end`, `totals`, `rows` (already top-N where configured).
4. Write the summary using the template below.
5. Call out **gaps** (empty slides, manual groups, data tagging issues) — do not hide zero rows.

## Output template

Use readable units (e.g. 23.0M m³, 9.0B ISK). Include the report period from JSON.

```markdown
# Town Hall Summary — [start date] to [end date]

Source: `town_hall_report --all --database production_readonly --period 30d`

## Capitals
Alliance-wide; top 5 shown. k/l/f = kills / losses / fleets.

| Group | Kills | Losses | Fleets | Highlights |
|-------|------:|-------:|-------:|------------|
| Dreads | … | … | … | … |
| Carriers | … | … | … | … |
| Faxes | … | … | … | … |

## Supply
### Mining
- Alliance: [volume] / [ISK] — top: …
- Roster (if run): [volume] / [ISK] — top: …

### Planetary Interaction — [total ISK]
Top 5: …

### Capital Production — [delivered/committed], [margin]
### Subcapital Production — [status or "empty"]
### Freighters — [contracts], [ISK], [m³], median [h]h
### Manual: Market, Loyalty Points

## Pulse
### Fleet Commanders — [total fleets]; top FCs: …
### Manual: Technology, Thinkspeak, Readiness, Advocates, Tournaments

## Slide readiness
| Ready | Empty / needs data | Manual |
|-------|-------------------|--------|
| … | … | … |

## Notes
- [Operational gaps, e.g. subcap orders not tagged, scope choice for mining]
```

## Known gaps to mention when relevant

- **Subcap production empty**: usually missing `IndustryOrder.tribe_groups` tags, not a broken query. Orders are tagged in Django admin only today.
- **Mining scope**: alliance vs roster shows different leaders; ask which the slide should use if unclear.
- **Freighters**: totals only, no per-pilot rows.
- **Fleet Commanders tribe**: town hall works alliance-wide; member view needs roster members in prod.
- **Capitals losses**: counted from victim killmails (lost qualifying hull). Requires deployed `capitals.py` fix.

## Production writes (not for summaries)

Read-only summaries use **`production_readonly`** or the report API on prod. Do **not** use `production_readonly` for backfills.

Backfill member activity event times on prod host:

```bash
docker compose -f docker-compose-prod.yml exec app \
  python3 manage.py backfill_tribe_activity_occurred_at --dry-run
```

## Reference

- Bindings and CLI docs: `backend/tribes/reports/README.md`
- Query implementations: `backend/tribes/reports/queries/`
- Read-only DB rules: `.cursor/skills/debug-production-readonly-db/SKILL.md`
