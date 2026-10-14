---
name: production-command
description: >-
  Formats commands to run on the production host via docker compose exec.
  Use when the user asks for a prod command, production shell, kickoff,
  docker-compose-prod, exec app, run manage.py on prod, or to trigger a
  Celery task in production.
---

# Production command

Give the user a **copy-paste command for the prod host**. Do not search the repo for this pattern. Do not run it from the local workspace (no SSH to prod from here).

For **read-only inspection from the laptop**, use [debug-production-readonly-db](../debug-production-readonly-db/SKILL.md) (`pipenv run` + `.using("production_readonly")`). Never write through that alias.

## Template

Prod path: `/home/minmatar/minmatar.org`. Compose file: `docker-compose-prod.yml`. Django service: **`app`**. Interpreter: **`python3`** (not `pipenv`).

```bash
docker compose -f docker-compose-prod.yml exec app python3 manage.py shell -c '...'
```

Management command:

```bash
docker compose -f docker-compose-prod.yml exec app python3 manage.py <command> [args]
```

Working dir on `app` is `/opt/minmatar` (backend already). Quote `-c` with **single quotes**; use double quotes inside Python.

## Kickoff vs inspect

| Need | Do |
|------|----|
| See a return value now (stats, counts) | Call the **Python helper** in `shell -c` and `print(...)` |
| Enqueue for workers | `Task.delay()` (respects `QueueOnce`; may no-op if already running) |
| Read-only from laptop | `production_readonly` locally — not this template |

Prefer the helper over `.delay()` when the user wants to confirm it ran.

## Services (do not exec the wrong one)

| Service | Use for |
|---------|---------|
| `app` | Django shell, `manage.py`, in-process kickoff |
| `celery` / `celery-eveonline` / `celery-market` | Live worker logs only |
| `beat` | Scheduler logs only |
| `bot` | Discord bot (`working_dir` `/opt/bot`) |

## Examples

Kick off NPSI poll and print stats:

```bash
docker compose -f docker-compose-prod.yml exec app python3 manage.py shell -c 'from fleets.helpers.npsi_ingest import poll_npsi_sources; print(poll_npsi_sources())'
```

Enqueue the Celery task instead:

```bash
docker compose -f docker-compose-prod.yml exec app python3 manage.py shell -c 'from fleets.tasks import poll_npsi_events; print(poll_npsi_events.delay())'
```

Management command:

```bash
docker compose -f docker-compose-prod.yml exec app python3 manage.py merge_supply_tribe --dry-run
```

## Output

Lead with the command. One line of what success looks like (e.g. `notified` ≥ 1). No extra deploy/SSH archaeology.
