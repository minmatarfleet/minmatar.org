# Runtime profiles

## Local development (default)

**One terminal:** from the repo root, run `./dev.sh` or `make dev`. This starts MariaDB/Redis, Django, Celery (all queues), Beat, frontend, and mobile.

| Component | How it runs |
| --- | --- |
| Everything above | `./dev.sh` or `make dev` from repo root |
| Django API only | `pipenv run python manage.py runserver` from `backend/` |
| Frontend only | `npm run dev` from `frontend/app/` |
| Celery / Beat / Discord bot | Individual commands in root `README.md` |

Uses your own Discord app and ESI credentials. See [developer data seeding](developer_data_seeding.md) for a fully populated database.

## Production

Everything runs in Docker via `docker-compose-prod.yml`: Django (gunicorn), frontend, Celery workers, Beat, bot, Redis, Mumble, Metabase, etc.

## Frontend-only (Astro dev)

Run `npm run dev` with `API_URL` pointing at the production API. No local backend required.

## Backend-only (Django dev)

Run Django locally with mocked ESI/Discord and synthetic test data (see `backend/README.md` standalone server section). MariaDB/Redis optional depending on what you are testing.
