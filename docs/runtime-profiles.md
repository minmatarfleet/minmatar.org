# Runtime profiles

## Local development (default)

| Component | How it runs |
| --- | --- |
| MariaDB + Redis | `docker compose up -d` from repo root |
| Django API | `pipenv run python manage.py runserver` from `backend/` |
| Frontend | `npm run dev` from `frontend/app/` |
| Celery workers, Beat, Discord bot | Same commands as root `README.md` (from `backend/` or `bot/`) |

Uses your own Discord app and ESI credentials. See [developer data seeding](developer_data_seeding.md) for a fully populated database.

## Production

Everything runs in Docker via `docker-compose-prod.yml`: Django (gunicorn), frontend, Celery workers, Beat, bot, Redis, Mumble, Metabase, etc.

## Frontend-only (Astro dev)

Run `npm run dev` with `API_URL` pointing at the production API. No local backend required.

## Backend-only (Django dev)

Run Django locally with mocked ESI/Discord and synthetic test data (see `backend/README.md` standalone server section). MariaDB/Redis optional depending on what you are testing.
