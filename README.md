# minmatar.org

Platform for Minmatar Fleet

# Technical Architecture

The [my.minmatar.org](https://my.minmatar.org/) site is built with a [JavaScript/Astro](https://astro.build/) front-end and a [Python/Django](https://www.djangoproject.com/) back-end. It is deployed as a set of [Docker](https://www.docker.com/) containers to a bare-metal cloud host using Docker Compose. The backend uses a MariaDB database, and there is also a Redis cache instance.

Authentication is handled via single-sign-on with [Discord](https://discord.com/), and the site also integrates with the [Eve Swagger Interface](https://esi.evetech.net/ui/#/).

The source code is hosted on GitHub, and the CI/CD pipeline is built using GitHub Actions. Operational monitoring is implemented using [Sentry](https://minmatar-fleet.sentry.io/).

# Prerequisites

## Installation
- Install Python
- Install Docker and Docker Desktop (Mac, WSL)
- Install Docker Compose
- Install `pyenv` on your machine (e.g `brew install pyenv`, google for other operating systems)
- Install `pipenv` on your machine (e.g `pip install --user --upgrade pipenv`)
- Install `pre-commit` on your machine (e.g `brew install`)
- Install libmariadb-dev or libmysqlclient-dev

## ESI
1. Go to https://developers.eveonline.com/
2. Create an application called `Local`
3. Set the callback URL to `http://localhost:8000/sso/callback`
4. Select all scopes

## Discord
- Create a discord server with this template: https://discord.new/eJBCDrW8kWgA
- Go to https://discord.com/developers/applications
- Create an application called `Minmatar - Local`
- Go to OAuth2 and add `http://localhost:8000/api/users/callback` and `http://localhost:8000/oauth2/login/redirect` to Redirects
- Go to Bot and enable it
- Go to OAuth2, select the "bot" scope, give it admin role, and copy the link it creates to invite the bot to your server

# Quickstart
## Frontend
1. `cp frontend/.env.example frontend/app/.env`
1. `cd frontend/app`
1. `npm i`
1. `npm run dev`

## Backend
1. `docker compose up -d` (sets up mariadb / redis)
1. `cp backend/.env.example backend/.env`
1. Fill out the EVE Online integratino section of `.env`
- `ESI_SSO_CLIENT_ID` is the client ID from https://developers.eveonline.com/
- `ESI_SSO_CLIENT_SECRET` is the client secret from https://developers.eveonline.com/
1. Fill out the Discord integration section of `.env`
- Go to your application from earlier https://discord.com/developers/applications
- `DISCORD_BOT_TOKEN` is under Bot > Reset Token
- `DISCORD_CLIENT_ID` is under OAuth2 > Client ID
- `DISCORD_CLIENT_SECRET`  is under OAuth2 > Client Secret
- `
- Go to your Discord client and enable Developer Mode under settings
- `DISCORD_GUILD_ID` is the ID when you right click your server icon and press Copy ID
- `DISCORD_PEOPLE_TEAM_CHANNEL_ID` (and other channel IDs) are from copy ID on channels, but you can just put it all to the same channel ID
1. `cd backend/`
1. `pipenv run python3 manage.py migrate`
1. `pipenv run python3 manage.py runserver`