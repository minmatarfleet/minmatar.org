# minmatar.org

Platform for Minmatar Fleet

# Technical Architecture

The [my.minmatar.org](https://my.minmatar.org/) site is built with a [JavaScript/Astro](https://astro.build/) front-end and a [Python/Django](https://www.djangoproject.com/) back-end. It is deployed as a set of [Docker](https://www.docker.com/) containers to a bare-metal cloud host using Docker Compose. The backend uses a MariaDB database, and there is also a Redis cache instance.

Authentication is handled via single-sign-on with [Discord](https://discord.com/), and the site also integrates with the [Eve Swagger Interface](https://esi.evetech.net/ui/#/).

The source code is hosted on GitHub, and the CI/CD pipeline is built using GitHub Actions. Operational monitoring is implemented using [Sentry](https://minmatar-fleet.sentry.io/).

# Local development

Docker is used for **infrastructure only**. Application code runs on your machine with normal commands.

| What | Where | Command |
| --- | --- | --- |
| MariaDB + Redis | repo root | `docker compose up -d` |
| Django API | `backend/` | `pipenv run python manage.py runserver` |
| Celery worker (default queue) | `backend/` | `pipenv run celery -A app worker -l info -Q celery` |
| Celery worker (EVE Online queue) | `backend/` | `pipenv run celery -A app worker -l info -Q eveonline` |
| Celery worker (market queue) | `backend/` | `pipenv run celery -A app worker -l info -Q market` |
| Celery Beat | `backend/` | `pipenv run celery -A app beat -l info` |
| Discord bot | `bot/` | `pipenv run python main.py` |
| Frontend | `frontend/app/` | `npm run dev` |

Use separate terminals for each process. Celery workers and Beat are only needed when you are testing background jobs or scheduled tasks.

Production deployment uses `docker-compose-prod.yml` and is unchanged.

Further setup: [Discord](docs/developer_discord_setup.md), [data seeding](docs/developer_data_seeding.md), [runtime profiles](docs/runtime-profiles.md). Auth architecture: [docs/auth/](docs/auth/README.md).

# Prerequisites

There is no separate prerequisites doc in this repo. Use the links below for tooling; project-specific steps are linked for ESI and Discord.

## Tooling

Install these before the quickstart. Versions match CI and `backend/Pipfile` unless noted.

| Requirement | Version | Install |
| --- | --- | --- |
| Python | 3.10 | [pyenv](https://github.com/pyenv/pyenv#installation) (recommended) or [python.org](https://www.python.org/downloads/) |
| Node.js | LTS (20+) | [nodejs.org](https://nodejs.org/) or [nvm](https://github.com/nvm-sh/nvm#installing-and-updating) |
| Docker | current | [Get Docker](https://docs.docker.com/get-docker/) (includes Compose on Mac/Windows; [Linux Compose install](https://docs.docker.com/compose/install/linux/) if needed) |
| Pipenv | latest | [pipenv installation](https://pipenv.pypa.io/en/latest/installation.html) |
| pre-commit | latest | [pre-commit installation](https://pre-commit.com/#install), then from repo root: `pre-commit install` |
| MariaDB client libs | system package | Required to build `mysqlclient` — [Django MySQL notes](https://docs.djangoproject.com/en/stable/ref/databases/#mysql-notes) (e.g. `sudo apt install libmariadb-dev` on Debian/Ubuntu) |

On WSL, use [Docker Desktop WSL integration](https://docs.docker.com/desktop/features/wsl/) or run Docker inside your WSL distro.

## ESI

Create a local EVE SSO application and add credentials to `backend/.env`. Official guide: [EVE SSO documentation](https://developers.eveonline.com/docs/services/sso/).

Project settings for local dev:

1. [Create an application](https://developers.eveonline.com/) named `Local`
2. Callback URL: `http://localhost:8000/sso/callback`
3. Select all scopes (or match what the app requires)

## Discord

See [docs/developer_discord_setup.md](docs/developer_discord_setup.md) for the full guide. Short version:
- Create a discord server with this template: https://discord.new/eJBCDrW8kWgA
- Go to https://discord.com/developers/applications
- Create an application called `Minmatar - Local`
- Go to OAuth2 and add `http://localhost:8000/api/users/callback` and `http://localhost:8000/oauth2/login/redirect` to Redirects
- Go to Bot and enable it
- Go to OAuth2, select the "bot" scope, give it admin role, and copy the link it creates to invite the bot to your server

# Quickstart

From the repo root:

1. `docker compose up -d` — starts MariaDB and Redis (creates the `minmatar` database on first run)

## Frontend
1. `cp frontend/.env.example frontend/app/.env`
1. `cd frontend/app`
1. `npm i`
1. `npm run dev`

## Backend
1. `cp backend/.env.example backend/.env`
1. Fill out the EVE Online integration section of `.env`
   - `ESI_SSO_CLIENT_ID` is the client ID from https://developers.eveonline.com/
   - `ESI_SSO_CLIENT_SECRET` is the client secret from https://developers.eveonline.com/
1. Fill out the Discord integration section of `.env`
   - Go to your application from earlier https://discord.com/developers/applications
   - Enable Developer Mode in Discord (User Settings → Advanced)
   - `DISCORD_BOT_TOKEN` is under Bot → Reset Token
   - `DISCORD_CLIENT_ID` is under OAuth2 → Client ID
   - `DISCORD_CLIENT_SECRET` is under OAuth2 → Client Secret
   - `DISCORD_GUILD_ID` is from right-click your server icon → Copy Server ID
   - `DISCORD_PEOPLE_TEAM_CHANNEL_ID` (and other channel IDs) are from Copy Channel ID; you can point them all at the same channel for local dev
1. `cd backend/`
1. `pipenv install --dev`
1. `pipenv run python manage.py migrate`
1. `pipenv run python manage.py runserver`

If the database user was never created (e.g. you had an old Docker volume from before init scripts), reset infra with `docker compose down -v` and run `docker compose up -d` again.
