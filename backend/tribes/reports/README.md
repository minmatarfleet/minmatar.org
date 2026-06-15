# Tribe catalog report bindings

Town hall and member metrics are bound to **catalog entries** (`TribeGroup.code`), not display names or hardcoded SQL.

## Layers

| Layer | Role | Location |
|-------|------|----------|
| **Catalog** | Which groups exist | DB fixtures + `TribeGroup.code` |
| **Ingest** | Member activity event log | `TribeGroupActivity` processors → `TribeGroupActivityRecord` |
| **Report bindings** | Which metrics apply, scope, source | `tribes/reports/registry.py` |
| **Report queries** | How to compute metrics | `tribes/reports/queries/` |
| **Presentation** | Top-N, CSV columns | Binding `presentation` + CLI/API |

Ingest and reporting are **separate**. Town hall slides use report queries (mining ledger, industry orders, freight program, fleet commanders). Member timelines use ingest where configured.

## Usage

```bash
# Single group (CSV matches Drive mining export columns)
pipenv run python manage.py town_hall_report \
  --group industry.mining --view town_hall --period 30d --format csv

# All automated bindings
pipenv run python manage.py town_hall_report --all --view town_hall --period 30d --format json
```

API: `GET /api/tribes/{tribe_id}/groups/{group_id}/reports/{view}?period=30d` (group chief / tribe chief auth).

## Registry

Bindings are keyed by `TribeGroup.code` in `REPORT_BINDINGS`. Manual Pulse narrative groups set `manual=True`. Capitals groups use qualifying ship types from group asset requirements.

## Event time

`TribeGroupActivityRecord.occurred_at` stores source event time when processors populate it. Metrics endpoints filter on `occurred_at` when set, else `created_at`. Backfill existing rows:

```bash
pipenv run python manage.py backfill_tribe_activity_occurred_at
```
