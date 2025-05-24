# minmatar.org

Platform for Minmatar Fleet

# Technical Architecture

The [my.minmatar.org](https://my.minmatar.org/) site is built with a [JavaScript/Astro](https://astro.build/) front-end and a [Python/Django](https://www.djangoproject.com/) back-end. It is deployed as a set of [Docker](https://www.docker.com/) containers to a bare-metal cloud host using Docker Compose. The backend uses a MariaDB database, and there is also a Redis cache instance.

Authentication is handled via single-sign-on with [Discord](https://discord.com/), and the site also integrates with the [Eve Swagger Interface](https://esi.evetech.net/ui/#/).

The source code is hosted on GitHub, and the CI/CD pipeline is built using GitHub Actions. Operational monitoring is implemented using [Sentry](https://minmatar-fleet.sentry.io/).

# Prerequisites

- Install Python
- Install Docker and Docker Desktop (Mac, WSL)
- Install Docker Compose
- Install `pyenv` on your machine (e.g `brew install pyenv`, google for other operating systems)
- Install `pipenv` on your machine (e.g `pip install --user --upgrade pipenv`)
- Install `pre-commit` on your machine (e.g `brew install`)
- Install libmariadb-dev or libmysqlclient-dev

# Hosts

To run this project behind the Nginx proxy, you must update your `/etc/hosts` file. Google the instructions for whatever your operating system is.

You need to add the following,

```
# Minmatar.org Local Development
127.0.0.1       api.local.minmatar.org
127.0.0.1       local.minmatar.org
```

# Quickstart

1. Copy the contents of `docker-compose-local.yml` into `docker-compose.yml`
2. Setup your `.env` file based on the `.env.example` file

- Create an application [here](https://developers.eveonline.com/) with CCP and get the ESI Client ID and ESI Secret Key
- By default the database user passwords are `example` for users `root` and `tools`, if you'd like this to be different update the relevant sections in `.env`, `docker-compose.yml`, and `dev/mariadb/setup.sql`
- Get the auth database password from BearThatCares

3. Generate a self signed tls key that will be used for the reverse proxy. `openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /etc/ssl/private/nginx-selfsigned.key -out /etc/ssl/certs/nginx-selfsigned.crt`

- these paths are the defaults in the compose file for mounting the tls certs. You can change these to be whatever you want.

4. Fetch the eve static export `wget https://www.fuzzwork.co.uk/dump/sqlite-latest.sqlite.bz2`, unzip it using `bunzip2 sqlite-latest.sqlite.bz2`, and move it `mv sqlite-latest.sqlite ./frontend/app/src/data`
5. Run `docker compose up -d` to create and start the containers. In the background this sets up the needed database users and database.

- Append the `--build app` flag to the compose command to rebuild the image if you've made code changes.

5. Navigate to https://localhost/api/ and you should also see the website (via the proxy)

This isn't a perfect setup and we're still working on streamlining it. If you have issues reach out to the technology team and we'll do our best to help.
Once you set this up once it will keep your db setup between development instances and you will only need to migrate if you change the database structure.

# Commands

- `for x in $(sed -e 's/#.*//' .env.local | grep '=') ; do export $x ; done` for populating env from .env

# Frontend Testing

For frontend unit testing we use vitest. To get started you can run `npm run test` in the ./frontend/ folder. This will start vitest and watch for any changes.
As you develop components you can use unit tests and snapshots to quickly test the expected output. If you make changes you can type `u` while vitest is running
to update the snapshots of the changed code. You can also run `make test` at the root to quickly run the test suite in docker.
