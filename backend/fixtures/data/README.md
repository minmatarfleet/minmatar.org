# Reference fixtures

Non-sensitive production configuration exported for local development.

## Prerequisites

1. Run migrations: `pipenv run python manage.py migrate`
2. Load EVE universe types locally: `pipenv run python manage.py eveuniverse_load_types`

## Load

```bash
pipenv run python manage.py load_reference_fixtures
```

Use `--clear` to remove existing reference rows before loading.

## Regenerate (maintainers with production_readonly access)

```bash
pipenv run python manage.py export_reference_fixtures
```

Files load in numeric order (`01_` … `09_`). Do not reorder without updating `fixtures/export.py` and `load_reference_fixtures`.
