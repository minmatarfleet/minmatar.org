# Reference fixtures

Non-sensitive production configuration exported for local development.

**Fittings are not included.** Doctrine fits, refits, and fitting history must
not be wiped or replaced by `load_reference_fixtures --clear`. Sync fittings
from production separately when needed (e.g. admin, or a dedicated sync
command).

## Prerequisites

1. Run migrations: `pipenv run python manage.py migrate`
2. Load EVE universe types locally: `pipenv run python manage.py eveuniverse_load_types`
3. Ensure required `EveFitting` rows already exist locally before loading
   doctrines / market expectations that reference them

## Load

```bash
pipenv run python manage.py load_reference_fixtures
```

Use `--clear` to remove existing reference rows before loading. This does
**not** delete fittings or refits.

## Regenerate (maintainers with production_readonly access)

```bash
pipenv run python manage.py export_reference_fixtures
```

Files load in numeric order (`01_` … `10_`). Do not reorder without updating `fixtures/export.py` and `load_reference_fixtures`.
