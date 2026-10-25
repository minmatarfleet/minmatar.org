#!/usr/bin/env bash
# Production deploy, run on the host from the repo root after `git pull`
# (.github/workflows/deployment.yml). See docs/architecture/deploys.md.
#
# Migrations run first in a one-off container, while the old app keeps
# serving. Then app and frontend are replaced with `docker rollout`: a new
# container starts next to the old one, edge starts routing to it once it is
# healthy, the old one is drained and stopped. A new container that never
# gets healthy is removed and the old one keeps serving. Everything else is
# recreated with `compose up`.
#
# On failure, the reason is written to DEPLOY_STATUS_FILE; the workflow posts
# it to Discord.
set -euo pipefail

# compose and docker-rollout read the files from COMPOSE_FILE; a local test
# can add an override file (docs/architecture/deploys.md).
export COMPOSE_FILE="${COMPOSE_FILE:-docker-compose-prod.yml}"
DEPLOY_STATUS_FILE="${DEPLOY_STATUS_FILE:-$HOME/.minmatar-deploy-status}"
ROLLOUT_VERSION=v0.14
ROLLOUT_SHA256=cdeaba6ae9eee3b0b606286e585bbda6787283d801a6ad6d9b9d2bc347fda05b
# Healthcheck interval (5s) x retries (3) for edge to drop the old container,
# plus time for its in-flight requests to finish.
PRE_STOP_HOOK="touch /tmp/drain && sleep 20"
# Migrations have already run, so a new container only has to boot.
HEALTHY_TIMEOUT=180
ROLLOUT_SERVICES=(app frontend)

step=""
released=()

report_failure() {
    local status=$?
    if [ "$status" -eq 0 ]; then
        rm -f "$DEPLOY_STATUS_FILE"
        return
    fi
    local still_up="The site is still on the previous release."
    if [ "${#released[@]}" -gt 0 ]; then
        still_up="Already on the new release: ${released[*]}. Everything else is on the previous one."
    fi
    local reason
    case "$step" in
        install) reason="docker-rollout could not be installed. Nothing was changed. $still_up" ;;
        build) reason="The images did not build. Nothing was changed. $still_up" ;;
        migrate) reason="Migrations failed. $still_up A MySQL migration that stopped partway is not rolled back, so check the schema." ;;
        rollout:*) reason="The new ${step#rollout:} container was not healthy within ${HEALTHY_TIMEOUT}s, so it was removed. $still_up" ;;
        recreate) reason="The first deploy with edge failed while recreating the stack. The site may be down." ;;
        others) reason="app and frontend are on the new release, but the workers, beat or bot did not restart." ;;
        prune) reason="The new release is live; only the image cleanup failed." ;;
        *) reason="The deploy failed (exit $status)." ;;
    esac
    echo "DEPLOY_REASON: $reason" > "$DEPLOY_STATUS_FILE"
    echo "==> $reason" >&2
}
trap report_failure EXIT

install_rollout() {
    local plugin="${DOCKER_CONFIG:-$HOME/.docker}/cli-plugins/docker-rollout"
    if [ -x "$plugin" ] && echo "$ROLLOUT_SHA256  $plugin" | sha256sum --check --status; then
        return
    fi
    echo "==> Installing docker-rollout $ROLLOUT_VERSION"
    mkdir -p "$(dirname "$plugin")"
    curl -fsSL "https://raw.githubusercontent.com/wowu/docker-rollout/$ROLLOUT_VERSION/docker-rollout" -o "$plugin.tmp"
    echo "$ROLLOUT_SHA256  $plugin.tmp" | sha256sum --check --status
    chmod +x "$plugin.tmp"
    mv "$plugin.tmp" "$plugin"
}

step=install
install_rollout

step=build
docker compose build

step=migrate
echo "==> Running migrations"
# traefik.enable=false: edge must never route to this one-off container.
docker compose run --rm --no-deps -l traefik.enable=false app \
    sh -c "python3 manage.py migrate --noinput && python3 manage.py sync_pilot_features"

if [ -z "$(docker compose ps --quiet edge)" ]; then
    # First deploy with edge: app and frontend still hold the host ports, so
    # this one is a plain recreate with a short outage.
    step=recreate
    echo "==> edge is not running, recreating the whole stack"
    docker compose up -d
else
    # No-op unless edge's own config changed.
    docker compose up -d --no-deps edge
    for service in "${ROLLOUT_SERVICES[@]}"; do
        step="rollout:$service"
        # docker rollout only replaces stopped containers when the service has
        # any (e.g. a `compose run` without --rm) and exits 0 without touching
        # the running one, so clear them first.
        stopped=$(docker compose ps -a --quiet --status exited --status created --status dead "$service")
        if [ -n "$stopped" ]; then
            echo "==> Removing stopped $service containers"
            # shellcheck disable=SC2086 # one ID per word
            docker rm $stopped
        fi
        echo "==> Rolling out $service"
        docker rollout --timeout "$HEALTHY_TIMEOUT" --pre-stop-hook "$PRE_STOP_HOOK" "$service"
        released+=("$service")
    done
    step=others
    mapfile -t others < <(docker compose config --services | grep -vxE "edge|$(IFS='|'; echo "${ROLLOUT_SERVICES[*]}")")
    docker compose up -d --no-deps "${others[@]}"
fi

# A local test sets KEEP_IMAGES=1 so it doesn't prune the machine's images.
step=prune
if [ -z "${KEEP_IMAGES:-}" ]; then
    docker image prune -a -f
    # Image prune leaves the build cache; a week of it keeps builds fast.
    docker builder prune -f --filter until=168h
fi
