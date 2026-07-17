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
  --group supply.mining --view town_hall --period 30d --format csv

# All automated bindings
pipenv run python manage.py town_hall_report --all --view town_hall --period 30d --format json

# Read-only production data (no writes; requires production_readonly in settings)
pipenv run python manage.py town_hall_report \
  --all --view town_hall --period 30d --database production_readonly
```

API: `GET /api/tribes/{tribe_id}/groups/{group_id}/reports/{view}?period=30d&scope=roster` (group chief / tribe chief auth). `scope` overrides the binding default (`roster` = tribe members, `alliance` = all linked pilots); only for reports that support both.

## Registry

Bindings are keyed by `TribeGroup.code` in `REPORT_BINDINGS`. Manual Pulse narrative groups set `manual=True`. Capitals groups use qualifying ship types from group asset requirements.

## Event time

`TribeGroupActivityRecord.occurred_at` stores source event time when processors populate it. Metrics endpoints filter on `occurred_at` when set, else `created_at`. Backfill existing rows:

```bash
pipenv run python manage.py backfill_tribe_activity_occurred_at
```

## Prod: Industry + Market → Supply merge

Catalog codes and fixtures already describe **Supply**. Live memberships/auth/Discord are migrated with a management command (not `migrate` / not `load_reference_fixtures --clear`).

```bash
# Dry-run (default): print planned renames + auth moves
docker compose -f docker-compose-prod.yml exec app \
  python3 manage.py merge_supply_tribe --dry-run

# Apply: ORM + Discord rename/add/remove via signals
docker compose -f docker-compose-prod.yml exec app \
  python3 manage.py merge_supply_tribe --apply
```

Idempotent. If one user looks wrong on Discord after apply:

```bash
docker compose -f docker-compose-prod.yml exec app \
  python3 manage.py shell -c 'from discord.tasks import sync_discord_user; sync_discord_user.run(USER_ID)'
```

Smoke: tribe list is Capitals / Supply / Pulse; Supply has seven active groups including **Market** (`supply.market`); Discord roles `Tribe - Supply` and `Tribe Group - Market`.
