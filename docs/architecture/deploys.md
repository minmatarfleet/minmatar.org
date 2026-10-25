# Deploys

Merging to `main` deploys production (`.github/workflows/deployment.yml`): the runner SSHes to the host, runs `git pull` and then `scripts/deploy.sh`. The website and API stay up during a deploy.

## How a deploy runs

`scripts/deploy.sh`:

1. Installs the [`docker rollout`](https://github.com/wowu/docker-rollout) CLI plugin (pinned version and checksum) if it is missing.
2. Builds every image while the old containers keep serving.
3. Runs `migrate` and `sync_pilot_features` in a one-off `app` container. The old containers keep serving. If this fails, the deploy stops before any container is replaced.
4. Replaces `app`, then `frontend`, with `docker rollout`:
   - A second container starts next to the old one. Once it is healthy, `edge` starts sending it requests.
   - The old container is drained (its healthcheck fails, so `edge` stops routing to it), given 20 seconds to finish in-flight requests, then stopped.
   - If the new container is not healthy within 3 minutes, it is removed and the old one keeps serving.
5. Recreates the other services (Celery workers, beat, bot, Redis, Metabase) with `docker compose up`, as before. The workers restart for a few seconds; visitors don't notice.
6. Prunes unused images and build cache older than a week. `docker image prune` alone never removed build cache, which had grown to 310 GB by October 2026.

When a step fails, the script writes one line saying what failed and whether the site is still on the previous release to `~/.minmatar-deploy-status`. The workflow reads it back and adds it to the Discord failure notice, with a link to the run.

## The pieces in `docker-compose-prod.yml`

- **`edge`** is a Traefik proxy. It owns the host ports `8020` (API) and `4321` (website), bound to `127.0.0.1` because only the host's nginx (a system package, `/etc/nginx/sites-enabled/api.minmatar.org` and `my.minmatar.org`) proxies to them, and routes only to healthy `app` and `frontend` containers. It finds them through the Docker socket and the `traefik.*` labels.
- **`app` and `frontend`** have no host ports, so two of each can run at once.
- **Healthchecks**: `backend/healthcheck.py` and `frontend/healthcheck.mjs`. A container is healthy once it answers an HTTP request; after that only its listening socket is checked, so a burst of slow requests can't mark the only container unhealthy. `/tmp/drain` fails the check, which is how a rollout drains the old container.
- **The `web` network** holds `frontend` and `edge`, and `app` there resolves to `edge`. If the frontend is built with `API_URL="http://app:8000"` (the `standalone.env` default), its server-side calls go through `edge` too and never reach an `app` container that is still starting. Production builds with `https://api.minmatar.org`, which goes through nginx and `edge` anyway. `frontend` is not on the default network.

`edge` trusts `X-Forwarded-*` headers from private addresses (the host nginx reaches it through the Docker bridge) and appends one hop to `X-Forwarded-For`. Compose sets `EDGE_PROXY_HOPS=1` on `app`, which adds that hop to `TRUSTED_PROXY_COUNT` (`backend/app/client_ip.py`), so `.env` keeps its value.

## Rules for changes

- **Migrations must work with the code that's already running.** The old containers keep serving after the migrations have run. Add columns and tables in one release; drop or rename them in a later one, after the code that reads them is gone.
- **Don't publish ports on `app` or `frontend`, or give them a `container_name`.** A rollout can't start a second container if you do. Send new traffic through `edge`.
- **Container names change with every deploy** (`app-1`, then `app-2`). `docker compose exec app ...` still finds the running one; don't hard-code the container name.
- **Changing `edge` itself** (Traefik version, entry points) recreates it, which drops connections for a second or two.
- **The host's nginx must proxy to `edge`**: `127.0.0.1:8020` and `127.0.0.1:4321`, as before. A proxy that reaches `app:8000` or `frontend:4321` over a Docker network bypasses `edge` and sees downtime again.
- **The first deploy after this change** recreates the whole stack once, because the old `app` and `frontend` still hold the host ports. It has the usual short outage.

## Testing a deploy locally

`scripts/deploy-test/override.yml` points `app` at the dev MariaDB from `docker-compose.yml` (set `DB_HOST=db` and a scratch `DB_NAME` in the root `.env`) and turns off the workers, beat, bot and Metabase. `scripts/deploy-test/probe.py` sends requests nonstop and reports every failure. From the repo root, with `.env`, `frontend/.env` (`API_URL="http://app:8000"`) and an empty `bot/.env` in place:

```bash
export COMPOSE_FILE=docker-compose-prod.yml:scripts/deploy-test/override.yml COMPOSE_PROJECT_NAME=rollouttest KEEP_IMAGES=1
./scripts/deploy.sh
python3 scripts/deploy-test/probe.py 150 http://127.0.0.1:8020/api/doctrines/ http://127.0.0.1:4321/ &
./scripts/deploy.sh
```

The first `deploy.sh` brings the stack up and the second is the rollout under test. `KEEP_IMAGES=1` skips the image prune, which would otherwise delete every unused image on your machine. When this was set up (October 2026), a recreate with the old compose file failed every API request for about 24 seconds; the rollout failed none of about 12,000, and a new `app` that never got healthy was rolled back with no failed requests.
