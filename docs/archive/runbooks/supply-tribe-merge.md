# Industry + Market → Supply tribe merge (archived runbook)

> **Archived.** A one-off production runbook from the July 2026 tribe merge (b6275df06), moved here from `backend/tribes/reports/README.md`. `merge_supply_tribe` is idempotent and still in the codebase.

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
