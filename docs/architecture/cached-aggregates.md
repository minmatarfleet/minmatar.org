# Cached aggregates

Pages such as the corporation profile, the product insights tab and the tribe About and Activity tabs show numbers that scan months of fleet attendance, killmails, skills or market history. On development data these queries look fast; on production data they took long enough to time a page out (the corporation page returned 502s when its aggregates ran per request). The rule: **a heavy aggregate is computed by Celery and only read in a request.** `backend/app/cache.py` holds the shared helper.

## The cache may fail

Redis is an accelerator, not a dependency. `cache_get`, `cache_set`, `cache_add` and `cache_delete` in `app/cache.py` log a warning and carry on when the cache raises, so a page renders without cached data instead of returning a 500. Use them instead of `django.core.cache.cache` in request code. (`eveonline/helpers/corporations/safe_cache.py` re-exports them for older imports.)

## CachedRollup

`app.cache.CachedRollup` is one cached value family: a key template, a TTL, a refresh-lock template and, for heavy rollups, the function that queues a refresh.

```python
STATS = CachedRollup(
    key="corporation_profile_stats:v2:{corporation_id}",
    ttl=6 * 60 * 60,
    lock_key="corporation_profile_stats:refreshing:{corporation_id}",
    lock_ttl=10 * 60,
    enqueue=_queue_refresh,   # queues the Celery task for these params
)
```

The templates are filled from the keyword arguments of each call. Pick one request-path policy per rollup:

| Policy | Use for | On a miss |
| --- | --- | --- |
| `get_or_queue(**params)` | Heavy scans | Never computes. The first caller queues one refresh (`cache.add` on the lock makes it single-flight across processes) and every caller gets `None` until the refresh calls `store(value, **params)`, which also releases the lock. The page renders without the data, or with an explicit warming state as the tribe Activity tab does (`warming: true`). |
| `get_or_compute(compute, **params)` | Light queries that are fine in a request | One caller computes and stores; concurrent callers wait up to `wait_seconds` for its result, then compute themselves. If the cache is down, everyone computes. |

Users today:

| Rollup | Module | Policy | Refreshed by |
| --- | --- | --- | --- |
| Corporation profile stats | `eveonline/helpers/corporations/stats_cache.py` | queue | `refresh_corporation_profile_stats`, every 2 hours |
| Product insights | `industry/helpers/product_insights.py` | queue | `refresh_product_insights_task`, every 2 hours (one lock for the whole pass) |
| Tribe About page | `tribes/helpers/about.py` | queue | `warm_tribe_about_pages`, every 3 hours |
| Tribe group Activity tab | `tribes/helpers/showcase.py` | queue | `warm_tribe_group_showcases`, twice an hour |
| Inferred monthly sales and volume | `market/helpers/inferred_sales_monthly.py`, `market/helpers/inferred_sales_monthly_volume.py` | compute | On request |
| Market endpoint responses | `market/endpoints/cache.py` | compute | On request |

## Conventions

- **Version the key** (`...:v2:...`) and bump the version whenever the cached shape changes, so a deploy never reads the old shape.
- **TTL longer than the refresh interval** for queued rollups, so a scheduled refresh replaces the value before it expires and readers rarely see a miss.
- **Lock TTL** a little longer than the refresh takes. If a worker dies, the lock blocks new refreshes until it expires.
- **Shared locks**: a pass that stores many values under one lock calls `store(..., release=False)` for each and `release()` once at the end.
- **Celery tasks that must not overlap** (a slow run still going when the next is due) use `app.locks.overlap_guard` or `single_flight`, which hold an owner token so a late run never releases its successor's lock. If the cache is down they run unguarded rather than not at all.

## Adding a heavy aggregate

1. Write `compute_...()` that builds the whole value from the database. Keep it out of the request path.
2. Define a `CachedRollup` with a versioned key, a TTL, a lock and an `enqueue` that queues the refresh task.
3. Add a task that computes and calls `store(...)`, and schedule it in `app/settings_celery.py` more often than the TTL.
4. In the endpoint, call `get_or_queue(...)` and return an explicit warming state on `None`; the frontend shows it instead of an error.
5. Check the query cost against production-scale data (`production_readonly`, read only), not just the dev database.
