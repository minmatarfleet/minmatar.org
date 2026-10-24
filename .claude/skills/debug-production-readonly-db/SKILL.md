---
name: debug-production-readonly-db
description: Query production data read-only for debugging via the production_readonly database alias. Use when debugging with production data, inspecting production state in Django shell, or when the user mentions production_readonly, read-only database, or querying production for debugging.
---

# Debugging with production_readonly Database

The project can define a second database alias **`production_readonly`** (`backend/app/settings.py.example`, built from `DB_READONLY_*` env vars by `readonly_database_from_env()` in `backend/app/settings_env.py`). It uses a read-only MySQL user: query real production data for debugging; never write to it.

## When to use

- Inspecting production-like data in Django shell or one-off scripts
- Reproducing bugs against real data without touching production writes
- Comparing behavior between `default` DB and production state

## How to query

Use `.using("production_readonly")` on querysets:

```python
from eveonline.models import EveCharacter

EveCharacter.objects.using("production_readonly").filter(user_id=123)
EveCharacter.objects.using("production_readonly").first()
```

Raw SQL:

```python
from django.db import connections
cursor = connections["production_readonly"].cursor()
cursor.execute("SELECT id, character_name FROM eveonline_evecharacter LIMIT 5")
cursor.fetchall()
```

## Rules

- **Never** create/update/delete via `production_readonly`. The DB user should have only `SELECT`, and the alias opens every session with `SET SESSION TRANSACTION READ ONLY`, so writes fail.
- Keep **`default`** for normal reads/writes; use `production_readonly` only when explicitly reading production data.
- In shell: `pipenv run python manage.py shell` then `.using("production_readonly")` as above.

## Configuration

Put these in `backend/.env` (listed, commented out, in `backend/.env.example`). Never put the credentials in `settings.py`:

- `DB_READONLY_USER`, `DB_READONLY_PASSWORD` — read-only MySQL user
- `DB_READONLY_HOST` — production or a read replica
- `DB_READONLY_PORT` (default `3306`), `DB_READONLY_NAME` (default `minmatar`)

The alias exists only when both `DB_READONLY_USER` and `DB_READONLY_HOST` are set. It is not used as a fallback for `DB_HOST`. Never set these on the production host itself.

If your local `backend/app/settings.py` predates this, re-copy it from `settings.py.example` (or add the same `readonly_database_from_env()` block) and move any hardcoded credentials into `.env`.

Check it is configured:

```bash
pipenv run python manage.py shell -c "from django.db import connections; print('production_readonly' in connections.databases)"
```
