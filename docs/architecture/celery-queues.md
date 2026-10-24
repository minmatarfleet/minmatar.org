# Celery queues

How background work is split across queues and workers, the rules every task follows, and how the queues are monitored. The code is the source of truth: `backend/app/queues.py` (routing), `backend/app/task_base.py` (the shared task base), `backend/app/monitoring.py` (Sentry), `backend/app/queue_health.py` (backlog checks). `backend/app/tests/test_queue_standards.py` fails the build when the rules below are broken.

## The queues

| Queue | For | Prod service | Replicas | Warns after |
| --- | --- | --- | --- | --- |
| `celery` (default) | Fast lane: critical, user-facing work that finishes in seconds | `celery` | 2 | 1 min |
| `feed` | zKillboard feed: live poll, rollups, clusters, affiliations | `celery-feed` | 1 (4 processes) | 2 min |
| `intel` | Intel affiliation database: sightings, zKill investigations | `celery-intel` | 1 | 30 min |
| `fleets` | Fleet tracking, implants, NPSI calendars, fleet reports | `celery-fleets` | 1 | 2 min |
| `campaigns` | FW campaigns: sweeps, polls, stats, lifecycle | `celery-campaigns` | 2 | 15 min |
| `eveonline` | ESI sync for characters, corporations, structures, tokens, SDE | `celery-eveonline` | 4 | 30 min |
| `market` | Market orders, contracts, prices, history, moon revenue | `celery-market` | 2 | 30 min |
| `industry` | Industry orders and jobs, LP store, LP and item buyback | `celery-industry` | 1 | 30 min |
| `community` | Discord, groups, tribes, applications, content, upkeep | `celery-community` | 1 | 30 min |

Worker services are defined in `docker-compose-prod.yml`. Each runs one process per host CPU unless the service sets `--concurrency`. Replicas were spread from the old layout so the total stays about the same. "Warns after" is the queue's `max_wait_seconds`: when its oldest message has waited longer, Sentry gets a warning (see [Monitoring](#monitoring)).

## Routing

`app.queues` decides every task's queue. The Celery router (`task_routes`) asks it, so it covers `delay`, `apply_async`, beat and `send_task` alike.

1. A task listed in `FAST_TASKS` goes to the fast lane (`celery`).
2. Otherwise the longest matching prefix in `ROUTES` wins (`market.` goes to `market`, `eveuniverse.tasks.update_market_prices` overrides `eveuniverse.`).
3. A task name with no route goes to `community` with a warning log. A registered task never gets there: the standards test fails first.

Nothing else picks a queue. Task decorators, beat entries and call sites never pass `queue=`.

### The fast lane

The default queue is reserved for work where a delay is a visible failure. A task joins `FAST_TASKS` only when all three hold:

- **Someone is waiting:** a pilot just did something, or a live event (a fleet starting, a structure under attack) needs a ping now.
- **It finishes in seconds:** one Discord or notification call, a small DB write. No ESI sync, no loops over characters or corporations.
- **It never fans out:** it doesn't queue more tasks.

Today that is the Discord outbox, notification delivery, Discord threads for applications and buyback/LP buyback orders, order-created notifications, the fleet schedule refresh and signup nudges, tribe guild sync, and the queue-health check. Anything else, even when it is user-triggered, goes to its feature queue. A heavier user-triggered job (a character refresh after adding it) waits behind that feature's scheduled work.

### Adding a feature queue

Give a feature its own queue when it is a major area with its own volume or latency needs: its scheduled work would delay other features, or its work would wait behind theirs. Small features share a queue by domain (`community`).

1. Add a `QueueSpec` to `QUEUES` and its prefixes to `ROUTES` in `backend/app/queues.py`. Pick `max_wait_seconds` (when Sentry should warn) and `dedupe_ttl_seconds` (how long a queued copy blocks the next one when the task has no `expires`).
2. Add a worker service to `docker-compose-prod.yml` (`<<: *celery-worker`, `-Q <queue>`). Take replicas from another service rather than growing the total until the host's capacity is known.
3. Add the queue to the all-queues worker in `dev.sh` and in the root `README.md`.
4. Add the queue to the table above.
5. Deploy. `docker compose up -d` doesn't stop a service that was removed or renamed: run `docker compose -f docker-compose-prod.yml up -d --remove-orphans` once on the host.

The standards test fails until steps 1 to 3 agree.

## Task standards

Every task's base class is `AppTask` (`backend/app/task_base.py`), set as the Celery app's `task_cls`, so `@app.task` and `@shared_task` both get it.

### What every task gets

- **One queued copy per call.** `delay`/`apply_async` drops a copy when the same task with the same arguments is already waiting (the returned result's state is `REJECTED`). `f(1)` and `f(item_id=1)` count as the same call. The lock is released when a worker starts the copy, so the next call can queue while it runs. It lasts the message's `expires`, or the queue's `dedupe_ttl_seconds` plus any countdown.
- **One run per message.** Redis hands a message out again when a worker held it past the visibility timeout (an hour), which happens to countdowns and rate-limited tasks. The second delivery is skipped.
- **An `enqueued_at` header**, which queue health uses to measure waits.
- **A `celery.queue` tag** on the run's Sentry scope.

Never deduped: retries (`self.retry`), chord and group members, linked callbacks, Celery's own `celery.*` tasks, and eager runs (tests). If the cache is down every guard lets the work through.

### Options

| Option | Use it when |
| --- | --- |
| `expires=<s>` | A copy that waited this long is stale. Required (as `expire_seconds` in the beat entry) for beat entries every 15 minutes or faster; set it on fan-out children to about their schedule interval. |
| `cooldown=<s>` | The same call must not run twice within this window however it was queued, e.g. per-character ESI polls. |
| `exclusive=<s>` | Two runs of the same call must never overlap. Set it to the longest expected runtime plus margin; a worker that dies holds it that long. |
| `dedupe=False` | Every copy is distinct work. A call site can pass `apply_async(..., dedupe=False)` for one call. |

### Rules

- **Never pass `queue=`** to `@app.task`, `apply_async` or a beat entry. Route in `backend/app/queues.py`.
- **Don't use `send_task`.** Use `app.signature("<task name>", args=[...]).delay()` when importing the task would be circular, so the call is deduped like any other.
- **Don't set `base=`** to QueueOnce or a custom class. `AppTask` covers it. django-eveuniverse's own tasks keep QueueOnce.
- **Fan out only work that will run.** A parent filters out entities its children would skip (no director with the scope, no token) instead of queueing them.
- **Don't re-queue yourself on transient failures** (ESI downtime, 429, a paused ESI budget). Return and let the next scheduled run pick it up. A retry that must happen soon uses `self.retry(countdown=...)`.
- **Throttle ESI with `eveonline.esi_budget`, not `rate_limit=`.** Celery rate limits apply per worker process, so the real limit changes with replicas and concurrency. Rate-limited messages are held unacked and can be handed out again.
- **Make tasks safe to run twice.** The guards make duplicates rare, not impossible (a cache outage, a lock that lapsed while a queue was backed up).

## Monitoring

Sentry is set up once in `backend/app/monitoring.py` for the web app, beat and workers. Beat and workers report to the Celery project (`SENTRY_CELERY_DSN`, falling back to `SENTRY_BACKEND_DSN`), because beat opens each cron check-in and the worker closes it.

### What is sent

| Signal | How | Where to look |
| --- | --- | --- |
| Errors | Every exception and `logger.error`, not sampled. django-esi's revoked-token noise is dropped. | Issues; filter by `celery.queue` or `component` (`web`, `beat`, `worker`) |
| Queue backlog | `app.tasks.monitor_queue_health` runs every minute on the fast lane. When a queue's oldest message waited past its `max_wait_seconds`, it sends one warning per queue per 15 minutes, fingerprinted per queue, with depth, wait and the oldest tasks. | Issues: "Celery queue X is backed up" |
| Queue gauges | `celery.queue.depth`, `celery.queue.oldest_wait` (per `queue`), `celery.queue.reserved` (messages held by workers), every minute | Metrics |
| Skipped copies | `celery.task.skipped` counter per `task` and `reason` (`already queued`, `redelivered`, `cooldown`, `still running`) | Metrics |
| Task latency and throughput | Celery spans carry the queue name and the time each message waited | Insights > Queues |
| Scheduled job health | Cron monitors for the schedules in `CRON_MONITORED_SCHEDULES`. Queue health is one: a missed check-in means beat or the fast-lane workers are down. | Crons |
| Traces and profiles | Sampled (below) | Performance, Profiles |
| Logs | WARNING and above | Logs |

### Sampling

Tuned for the free plan. Set these on the host to change them without a code change:

| Variable | Default | Applies to |
| --- | --- | --- |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.2` | Web requests and tasks |
| `SENTRY_TICK_TRACES_SAMPLE_RATE` | `0.02` | Beat entries every minute or faster |
| `SENTRY_PROFILES_SAMPLE_RATE` | `0.1` | Share of traced transactions that are profiled |
| `SENTRY_LOGS_LEVEL` | `WARNING` | Lowest log level sent to Sentry Logs |

A task queued from a sampled request or task is traced too, so a trace follows the work across queues.

### Adding a cron monitor

Add the beat entry's name to `CRON_MONITORED_SCHEDULES`. Each monitor counts against the plan, so keep it to jobs whose silent failure would hurt: weekly or daily jobs nobody watches, and the queue-health heartbeat.

## Operations

`manage.py celery_queues` reads and repairs the queues. On the production host:

```bash
docker compose -f docker-compose-prod.yml exec app python3 manage.py celery_queues status
```

- `status`: depth, oldest wait and top tasks per queue, flagged when backed up.
- `dedupe`: drops queued duplicates of the same call (task, args and kwargs), keeping the copy that would run first. A dry run unless `--apply`. It runs atomically inside Redis and blocks it for about 2.5s per 15k queued messages; above about 25k, Redis answers BUSY to workers until it finishes. Fast-lane tasks are never touched.
- `clear-locks [--task <name>]`: forgets "already queued" locks. Run it after purging a queue (`celery -A app purge -Q <queue>`), or calls whose copy was purged stay blocked until their lock expires.

Backed up? Run `status` first. A queue full of one task usually means a fan-out that should filter or expire its children. A queue that is deep with varied work needs more replicas.
