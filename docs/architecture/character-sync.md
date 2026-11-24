# Character sync

How the site keeps each character's ESI data fresh: a refresh interval per data type ("section"), audiences that change the interval, one paced scheduler, and a freshness row per character and section.

Code: `backend/eveonline/character_sync.py` (sections, audiences, stamping, inline runs), `backend/eveonline/tasks/character_sync.py` (scheduler, sync task, health), `backend/eveonline/character_sync_signals.py` (triggers), `backend/eveonline/models/character_sync.py` (`EveCharacterSyncState`).

## Why

Until November 2026, `update_alliance_characters` queued `update_character` for every member at :37 every 4 hours. `update_character` refreshed every section and had `rate_limit="5/m"`, which Celery counts per worker container.

- **The queue backed up every cycle.** With 4 `celery-eveonline` replicas that's about 20 characters a minute, so the roughly 2,800-character run took about 140 of every 240 minutes to drain.
- **Everything else on `eveonline` waited behind it.** The notification poller starved behind it after #3110 (fixed in #3111), and new characters' first fetch waited up to 2 hours.
- **One interval for everything:** skills and blueprints were fetched as often as assets.
- **No record of freshness or failure.** Nothing recorded how fresh anything was or whether a fetch had failed.

## Refresh intervals

"Members" are every character with a token, not `esi_deleted`, belonging to a user with a character in a tracked alliance (`tracked_alliance_ids()`).

| Section | Default (members) | Faster audiences | Notes |
| --- | --- | --- | --- |
| Assets | 4 h | — | Buyback reads M-EXC's corp hangar, not character assets (below) |
| Contracts | 4 h | **1 h** if the character owns an open industry order | Reconcile is queued only for owners of an open order |
| Industry jobs | 4 h | **1 h** for characters with an undelivered assignment on an open order, and their user's other characters | Replaces `sync_industry_jobs_for_order_assignees` in scheduled mode |
| Killmails | 24 h | **15 min** while on an active fleet, plus 30 min after it ends | Fleet fights use the zKill feed, not this |
| Mining ledger | 24 h | Tiered by how likely new rows are (below) | Fixed per-pilot slot instead of jitter |
| Skills (+ readiness re-rate) | 24 h | — | The tribes refresh button refreshes on demand |
| Clones and implants | 24 h | — | Fleets poll implants live separately |
| Blueprints | 24 h | — | |
| Planets | weekly | **72 h** for active members of the PI tribe group (`supply.planetary-interaction`) | |

- **Mining ledger tiers** (first match wins):

  | Tier | Who | Interval |
  | --- | --- | --- |
  | Hot | a pull found new ore in the last 25 min (`EveCharacterMiningDelta`) | 10 min |
  | In fleet | on an active fleet, plus 30 min after it ends | 15 min |
  | Warm | ledger rows today or yesterday | 1 h |
  | Cool | ledger rows in the last 30 days | 6 h |
  | Default | everyone else, including characters with no skills synced | 24 h |
  | Unlikely | skills synced, but none of Mining Frigate, Expedition Frigates, Mining Barge, Exhumers or Ice Harvesting | 72 h |

  A pull that finds new ore stamps the pilot Hot straight away. A Hot pilot drops back after about three empty pulls. ESI caches the ledger for about 10 minutes, so pulling faster gains nothing. On leave slows only Default and Unlikely pilots. The skill sets are cached for an hour (`MINING_SKILLS_CACHE_KEY`).
- **Mining slots:** a successful mining pull is next due at the pilot's fixed slot within the interval (`next_slot`: the golden-ratio fraction of the character ID), between half and one and a half intervals away. Pilots spread evenly over the interval, and the landing page's mining lines come in staggered rather than in bursts.
- **On leave:** characters of users whose `UserCommunityStatus` is On Leave or Alumni use 72 h for every section. A section that is already longer (planets, weekly) keeps its own interval.
- **Priority:** active fleet, then industry, then on leave, then the default.
- **Industry characters outside the members:** the 1 h audiences are kept fresh even when the character isn't a member, but only for that one section.
- **Applicants and other non-members:** every section is fetched once when the character is added (`update_character_urgent`), and not again until the affiliation sync puts them in a tracked alliance.
- **Unchanged jobs:** public data (`update_all_character_public_data`, every 8 h) and corporation history (`queue_stale_character_corporation_history`, 24 h TTL, every character) keep their own jobs, because both cover every character, applicants included.

## How it works

### Sections and outcomes
`SECTIONS` lists each section's name, required token scopes, refresh function and follow-ups, default interval and cost weight. Assets and blueprints weigh 3, planets and killmails weigh 2, and the rest weigh 1.

A section's outcome comes from the ESI responses it saw. `eveonline.client.record_esi_outcomes()` collects the `response_code` of every `EsiResponse` built while the section runs, so the existing helpers didn't need to change.

| Outcome | From | Stamp |
| --- | --- | --- |
| ok | only successes | `synced_at` = now; `next_due_at` = now + interval ± 10% |
| no scope / suspended | missing scope, 902/904/905 | `next_due_at` = now + interval |
| failed | a 4xx for this character | retry in 30 min, or after the full interval once 3 failures in a row |
| transient | 5xx, 906, an exception | retry in 15 min (full interval after 3 in a row); the run stops |
| error limit | 420, or our ESI budget paused or low | not stamped; the run stops |

`EsiClient` reports django-esi 4xx and 420 responses to `esi_budget.observe_response`. Before, only `esi_http` routes reached the app-wide error budget. `budget_observed` stops `esi_budget.note_response` from counting the same response twice.

### Freshness rows
`EveCharacterSyncState` has one row per character and section:
- **Fields:** `next_due_at`, `queued_at`, `attempted_at`, `synced_at`, `last_error`, `consecutive_failures`.
- **Index:** (`section`, `next_due_at`).
- **Interval:** worked out when the row is stamped, using the audiences, so the scheduler only compares `next_due_at` with now.

### The run
`run_character_sync(character, sections=None, force=False, lock=True)`:
1. Takes a per-character lock (`character-sync:<pk>`), so the scheduled task and `update_character` never overlap.
2. Skips during ESI downtime.
3. Runs the due sections in order, and stamps each one as it returns.

A character with no attempted rows is always forced. `update_character`, which is used by fanout mode, new characters and the tech router, runs every section with `force=True`. The tribes refresh button runs assets and skills inline with `lock=False`, because its response is built from the fresh data.

### The scheduler
`queue_due_character_syncs` runs every minute, in shadow and scheduled modes. (It ran every 5 minutes until November 2026; in production every queued sync then started in the first seconds of the tick, so ESI calls came in bursts.) Each tick:
1. Skips during downtime or a paused ESI budget.
2. Loads the audiences once.
3. Picks characters, never-synced first: members with no rows, and characters added in the last 7 days whose first fetch was never attempted (after a 10-minute grace period).
4. Then picks due rows (`next_due_at <= now`, not queued in the last 15 minutes), oldest first.
5. Pushes due rows of characters that left every audience a day out.
6. Takes characters until its share of the weighted budget is reached: `CHARACTER_SYNC_COST_PER_TICK` (default 300) is a budget per 5 minutes, so each one-minute tick spends a fifth (`tick_budget()`).
7. Marks their rows queued, then queues `sync_character_sections(character_id)`, spread across the minute.

### Triggers (`character_sync_signals.py`)
Each trigger only moves `next_due_at` earlier:
- **A new industry assignment:** industry jobs for the assignee's characters.
- **A new industry order:** the owner's contracts.
- **A pilot joining a fleet:** killmails and mining, 15 minutes later.
- **A user coming back from leave:** every section.

### Freight and buyback
Both read corporation data, so they have their own tasks every 10 minutes:
- **`eveonline.tasks.corporations.sync_freight_contracts`:** the freight corporation's contracts. Before, they refreshed hourly inside the rate-limited `update_corporation`.
- **`buyback.tasks.sync_buyback_contracts_task`:** M-EXC's contracts and the contract ledger.
- **Buyback hangar:** the snapshot stays in the hourly `sync_buyback_ledger_task`, because ESI caches corporation assets for an hour.

### Affiliations
- **Schedule:** every 15 minutes, was 30.
- **Bulk loading:** characters are loaded in bulk per batch instead of one `.get()` per result.
- **Membership changes:** a changed user still queues `groups.update_affiliation` straight away.

## Modes and rollout

`CHARACTER_SYNC_MODE` (`app/settings_common.py`, from the environment) defaults to `fanout`. Changing it needs a restart of workers and beat.

| Mode | 4-hourly fan-out | Assignee jobs sync | Scheduler |
| --- | --- | --- | --- |
| `fanout` | runs, spread across 4 h in 5-minute slots, skipping characters updated in the last 3.5 h | runs | does nothing |
| `shadow` | runs | runs | logs each tick's plan, writes nothing |
| `scheduled` | returns early | returns early | queues |

Fanout mode already fixes the backlog, because the rate limit is gone and the run is spread out. It also records freshness rows on every update.

Rollout:
1. **Deploy (fanout).** Check that `eveonline` drains between runs. Watch ESI error-budget dips, and the freight and buyback 10-minute syncs. After a day, `manage.py character_sync_status` shows the fanout baseline.
2. **`shadow` for 2 days.** Read the "Character sync shadow tick" logs: due counts per section, cost against the budget, and oldest due age. Tune `CHARACTER_SYNC_COST_PER_TICK` if needed.
3. **Run `manage.py spread_character_sync`**, then set `scheduled`. Spreading moves every in-scope row's `next_due_at` evenly across its interval, so day one isn't one spike.
4. **Rollback:** set `fanout` and restart. Already-queued scheduler messages still run once, which is harmless.

## Monitoring
- **`manage.py character_sync_status`:** per section, the in-scope count, overdue count (older than twice the interval), failing count, p95 and oldest age, and top errors. Also new characters whose first fetch was never attempted.
- **`report_character_sync_health`, every 15 min:** sends Sentry gauges `character_sync.overdue_ratio` and `character_sync.p95_age_hours`. In scheduled mode it warns when more than 5% of a section is overdue, or when a new character has no first fetch after 10 minutes.
- **The scheduler:** gauges `character_sync.due` (per section) and `character_sync.queued`.
- **Cron monitor:** follows `CHARACTER_SYNC_MODE` (`app.monitoring.monitored_schedules`): the 4-hourly fan-out in fanout mode, the scheduler in scheduled mode, both in shadow mode. The schedule that returns early in a mode has no monitor.
- **Queue limit:** `eveonline`'s 30-minute queue warning should now stay quiet.

## What counts as a regression
1. A section's p99 age is above 1.5 × its interval.
2. Total ESI calls per hour rise.
3. More error-budget dips or 420s.
4. A section stops refreshing for an in-scope character that has the scope.
5. An in-scope character drops out.
6. A new character's first fetch is slower than before.
7. Affiliation runs overlap.
8. An open-order owner goes more than 1.5 h without a contracts fetch, or an assignee without a jobs fetch.
9. Freight or buyback contracts go more than 20 minutes without a sync.
10. A pilot on an active fleet goes more than 30 minutes without a killmail or mining fetch.

## Follow-ups
- **Two weeks after `scheduled`:** remove `fanout` and `shadow` modes, `update_alliance_characters` and `sync_industry_jobs_for_order_assignees`, with a migration deleting their `PeriodicTask` rows. Drop the public-data call from `update_character`, and move the remaining callers to `run_character_sync`.
- **`update_corporation` and `sync_corporation_projects`** still use `rate_limit`. Move them to `esi_budget`.
- **ETags for character endpoints** (django-esi raises on 304) would make unchanged sections nearly free.
