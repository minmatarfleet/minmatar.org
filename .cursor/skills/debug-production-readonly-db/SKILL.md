---
name: debug-production-readonly-db
description: Query production data read-only for debugging via the production_readonly database alias. Use when debugging with production data, inspecting production state in Django shell, or when the user mentions production_readonly, read-only database, or querying production for debugging.
---

# Debugging with production_readonly Database

The project has a second database alias **`production_readonly`** (see `backend/app/settings.py`). It uses a read-only MySQL user: query real production data for debugging; never write to it.

## When to use

- Inspecting production-like data in Django shell or one-off scripts
- Reproducing bugs against real data without touching production writes
- Comparing behavior between `default` DB and production state

## How to query

Use `.using("production_readonly")` on querysets:

```python
from eveonline.models import Character

Character.objects.using("production_readonly").filter(user_id=123)
Character.objects.using("production_readonly").first()
```

Raw SQL:

```python
from django.db import connections
cursor = connections["production_readonly"].cursor()
cursor.execute("SELECT id, character_name FROM eveonline_character LIMIT 5")
cursor.fetchall()
```

## Rules

- **Never** create/update/delete via `production_readonly`. The DB user has only `SELECT`; writes are not allowed.
- Keep **`default`** for normal reads/writes; use `production_readonly` only when explicitly reading production data.
- In shell: `pipenv run python manage.py shell` then `.using("production_readonly")` as above.

## Configuration

Env vars (no credentials in code):

- `DB_READONLY_USER`, `DB_READONLY_PASSWORD` — read-only MySQL user
- `DB_READONLY_HOST`, `DB_READONLY_PORT` — optional; default to `DB_HOST` / `DB_PORT`

Same database name as default (`DB_NAME`); host is typically production or a read replica.
