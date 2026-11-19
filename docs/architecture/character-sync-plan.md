# Character sync: a refresh interval per data type, paced by one scheduler

Status: plan, November 2026, checked against `main` at `ed22fbc5c`. Follows the #3110 deploy, where the `eveonline` queue was 1,608 deep and the notification poller starved behind it (fixed separately in #3111).

## What exists today

Several jobs already pull character data, each with its own cadence, audience and pacing.

| Job | Schedule | Audience | What it fetches | Pacing |
| --- | --- | --- | --- | --- |
| `update_alliance_characters` → `update_character` | :37 every 4 h | Every character of every user with a character in a tracked alliance, with a token, not `esi_deleted` | Public data, assets, skills (+ readiness re-rate), killmails, contracts (+ industry reconcile), industry jobs (+ job notifications), mining, planets, blueprints, clones+implants | `rate_limit="5/m"` per worker container |
| `update_character_urgent` (`eveonline/signals.py`) | When an `EveCharacter` is created with a token | That character | Same as above | None (calls the function inline) |
| `tech` router | Admin action | One user's characters | Same as above | None |
| `tribes…post_membership_characters_available_refresh` | Pilot button | One character | Assets and skills | 1 h cooldown per character (cache key) |
| `update_all_character_public_data` | :20 every 8 h | Every character not `esi_deleted` | Public data | One long task, inline loop |
| `queue_stale_character_corporation_history` → `sync_character_corporation_history_task` | :05 and :35 | 50 characters per run with stale `corporation_history_synced_at` (24 h TTL) | Corporation history | Stamp + stale batch, `rate_limit="10/m"` |
| `update_character_affilliations` | :00 and :30 | Every `EveCharacter` | Affiliations, bulk, 1,000 per call | One task; per-result `.get()`; queues `groups.update_affiliation` per changed user |
| `groups.update_affiliations` / `applications.accept_applications_of_members_task` | :15 and :45 | Every user / pending applicants | Nothing from ESI; full reconcile sweeps | — |
| `industry.sync_industry_jobs_for_order_assignees` → `sync_industry_jobs_for_character` | :05 every 4 h | Every character ever assigned to an order item, plus their user's other characters | Industry jobs (+ job notifications) | `cooldown` 1 h |
| `industry.reconcile_industry_contract_associations_task` | :35 every 2 h | — | Nothing from ESI; matches stored contracts to orders | — |
| `campaigns.poll_campaign_recent_killmails` | 30 min | Enlisted campaign characters | Recent killmails missing from `FeedKillmail`, into the feed | `esi_budget` `char-killmail` bucket |
| `market.fetch_attributed_market_orders` | 30 min | Market-scoped characters of eligible tribe members | Character market orders | Per-character tasks |
| `fleets.poll_active_fleet_implants` | 10 min | Members of qualifying live fleets (`members_to_poll`) | Implant snapshots | Spread with countdowns |
| `eveonline.tasks.notifications` | Every minute, a tenth of the roster | Characters with the notification scope | Notifications | Minute buckets (`character_id % 10`), `esi_budget` |

Facts that shape the design:
- **Two stamps already exist:** `EveCharacter.clones_synced_at`, written only by the clones helper, and `corporation_history_synced_at`. The corporation-history job already works the way this plan proposes (stamp, then sync a stale batch on a schedule), at small scale.
- **The section helpers don't use `esi_budget`.** In particular, `update_character`'s killmail fetch spends the same `char-killmail` ESI bucket as the campaigns poll, but that spend isn't tracked, so the two can starve each other.
- **ETags are off** for character endpoints (`eveonline/client.py`; django-esi raises on 304), so every sync is a full fetch.
- **Two tasks on `eveonline` use `rate_limit`:** `update_character` and `sync_character_corporation_history_task`. `docs/architecture/celery-queues.md` already says to throttle ESI with `esi_budget` instead.
- **Industry jobs are already fetched twice** for most assignees: once by the industry job, once by the member sync. The industry audience is every character ever assigned, not just characters on open orders.

## Problem

- **One interval for everything.** 4 hours was picked to fit most cases broadly. Skills, blueprints and mining don't need it; assets, contracts and industry jobs, which other features depend on, do.
- **The pace depends on replica count.** `rate_limit` is per worker container: 4 `celery-eveonline` replicas means about 20 characters a minute.
- **The queue is backed up most of the time.** The 20:37 run on 2026-11-19 queued roughly 2,800 characters, an estimate from 1,608 still waiting after about an hour. That takes about 140 minutes to drain out of each 240-minute cycle. Past roughly 4,800 characters it never drains.
- **Everything else on `eveonline` waits behind it**, including a new character's first fetch (applicants included) and corporation syncs.
- **The queue-health warning is noise.** It fires every 4 hours during normal running.
- **Downtime makes it worse.** `update_character` re-queues itself with a countdown during ESI downtime, so the pile moves to 11:15.
- **Overlapping jobs** (industry jobs, public data, killmails) fetch the same data on separate schedules, and nothing records how fresh any section is.

## Goals: up to date, within reason

### Refresh interval per section (members)

"Members" keeps today's scope. ESI cache is how long ESI serves the same answer; fetching more often than that returns nothing new.

| Section | What reads it | ESI cache | Today | Proposed |
| --- | --- | --- | --- | --- |
| Affiliations (bulk, every character) | Alliance scope, groups and Discord roles, application auto-accept | verify in Phase 0 | 30 min | **15 min** |
| Assets | Fleet ship pickers and hangars, industry, tribes (hull checks), tech | 1 h | 4 h | **4 h** |
| Contracts | Industry order delivery (reconciled every 2 h), market | 5 min | 4 h | **4 h**; **1 h** for characters on an open industry order |
| Industry jobs, plus "job detected" notifications | Industry orders | 5 min | 4 h, twice | **4 h**; **1 h** for characters on an open industry order. Replaces `sync_industry_jobs_for_order_assignees` |
| Skills, plus readiness re-rate | Capabilities and fleet readiness, Training tab, tribes, applications | 2 min | 4 h | **24 h**, plus the pilot refresh button |
| Clones and implants | Industry, character pages (fleets poll implants live separately) | 2 min | 4 h | **24 h** |
| Killmails | Activity, timezones, tribes, applications, reports. Fleet fights use the zKill feed; campaigns poll enlisted characters every 30 min | 5 min | 4 h | **24 h** |
| Mining ledger | Mining stats (alliance, tribes, industry); ESI keeps 30 days | 10 min | 4 h | **24 h** |
| Planets | Industry and PI | 10 min | 4 h | **24 h** |
| Blueprints | Industry | 1 h | 4 h | **24 h** |
| Corporation history | Corp pages, applications | — | 24 h TTL (own job) | **24 h**, moved into the registry |
| Public data | Sec status and similar | — | 4 h plus 8 h | **8 h**, own task only |

The "What reads it" column comes from where each model is imported. Confirm it per section before the flip.

Alert when more than 5% of a section's in-scope characters are older than twice its interval.

### Other characters (unchanged)

| Who | Target | Alert when |
| --- | --- | --- |
| A newly added character, applicants included | Every section once, within a minute (`update_character_urgent`) | Not synced 10 min after it was added |
| Applicants after that, and everyone else outside member scope | Not synced. Applicants join the member intervals when the affiliation sync puts them in a tracked alliance. | — |

`esi_deleted` and `esi_suspended` characters stay skipped. `tech` and the tribes refresh button keep working on demand.

### ESI load
- **Today:** about 2,800 characters × 6 syncs a day × 10 sections, plus the industry job's duplicate fetches. Roughly 170,000 section fetches a day.
- **Proposed:** 3 sections every 4 h and 6 daily is 24 a day per character, roughly 67,000. The 1 h tier for open industry orders adds 2 × 18 extra fetches a day per character on an open order (a few hundred characters at most; measure in Phase 0).

## Design

### 1. Record freshness per section
New model `EveCharacterSyncState`:
- **Fields:** `character` FK, `section`, `attempted_at`, `synced_at`, `last_error`.
- **Constraints:** unique on (`character`, `section`), index on (`section`, `attempted_at`).

Existing stamps:
- **`corporation_history_synced_at`** stays, because `queue_stale_character_corporation_history` reads it until that job moves into the registry in Phase 4.
- **`clones_synced_at`** stays as is; nothing else reads it.

### 2. A section registry
`eveonline/character_sync.py` lists each section with:
- its name and required token scopes (the `SCOPE_*` constants from `eveonline/tasks/characters.py`);
- its refresh function, including today's follow-ups (contract reconcile, job notifications, readiness re-rate);
- its ESI budget group, where one exists;
- a function that returns its interval for a character. Most are fixed. Contracts and industry jobs return 1 h when the character's user has an open industry order assignment.

`update_character`, `update_character_urgent`, `tech` and the tribes refresh button all go through the registry, so everything stamps the same rows.

### 3. One scheduler sets the pace
`queue_due_character_syncs` runs every 5 minutes.

Each tick:
1. For each section, finds in-scope characters with the scope whose `attempted_at` is older than the interval, or with no row yet.
2. Groups them by character.
3. Orders by most overdue relative to the interval, never-synced first.
4. Takes characters until it reaches `CHARACTER_SYNC_SECTIONS_PER_TICK` section fetches (default 300; the steady state is about 235).
5. Queues `sync_character_sections(character_id, sections)` with countdowns spread across the 5 minutes.

Why timestamps instead of the notifications poller's minute buckets: buckets spread a single fixed interval with no stored state, but sections here have different intervals, need catch-up after downtime, and need a visible "how stale" number.

### 4. The sync task
`sync_character_sections(character_id, sections)` runs the registry functions in today's order and stamps each section.

- **No Celery rate limit.** Pace comes from the scheduler.
- **ESI downtime:** returns without re-queuing; the next tick after 11:15 picks the character up.
- **Error budget:** before each section it checks `esi_budget.error_budget()`. Below the floor it stops, and the remaining sections stay due.
- **Bucketed groups:** the killmail section spends through `esi_budget` (`char-killmail`), so it and the campaigns poll share one ledger.
- **Error-limit abort:** an `ESIErrorLimitException` stamps the attempt for that section only, so a broken token waits a full interval.

### 5. Affiliations every 15 minutes
- **Schedule:** change the beat entry from `minute="0,30"` to every 15 minutes, with `expire_seconds` set to 15 minutes.
- **Bulk loading:** load characters in bulk instead of one `.get()` per result. The task covers every `EveCharacter`, not just members.
- **What 15 min buys:** a changed user is already queued for `groups.update_affiliation` immediately, so membership changes reach groups and Discord within about 15 minutes. The :15/:45 sweeps (`groups.update_affiliations`, application accept) stay as safety nets.
- **ESI cache check:** if Phase 0 shows ESI caches affiliations for an hour, 15-minute polling mostly re-reads the cache. Decide with that number in hand.

### 6. Pilot refresh button
The tribes endpoint already lets a pilot refresh assets and skills once an hour per character. Move it onto the registry: same 1 h cooldown, queued as `sync_character_sections` instead of inline helper calls. This is the escape hatch for daily skills.

### 7. Fleet activity: not built yet
Nothing reads character killmails or mining per fleet today:
- Fight reports use the zKill feed.
- Activity, timezones and tribe reports are fine with daily data.

Build it when a consumer needs it. It would be a ~20-line job queued from `settle_fight_timeline` that calls `sync_character_sections(c, ["killmails", "mining"])` for the fleet's `EveFleetInstanceMember` characters, using the same member lookup as `fleets.helpers.active_clones`.

### 8. New characters stay immediate
`update_character_urgent` keeps running every section when a token is added, and stamps them. With `eveonline` drained every tick it runs within about a minute.

### 9. Visibility
- **Status command:** `manage.py character_sync_status` prints, per section, the in-scope count, overdue count, p95 age and oldest age. It also lists characters added in the last day with nothing synced.
- **Sentry:** a check beside `monitor_queue_health` warns on the alert thresholds above.
- **Cron monitor:** the scheduler gets a Sentry cron monitor (`CRON_MONITORED_SCHEDULES`), replacing the old fan-out's entry at cleanup.
- **Queue limit:** `eveonline`'s 30-minute warning stays and means something again.

## What counts as a regression

Checked with `character_sync_status` and Sentry before each phase:

1. A section's p99 age goes above 1.5 × its interval.
2. Total ESI calls per hour rise.
3. ESI error-budget dips (`esi_budget.snapshot()`) or 420s become more frequent.
4. A section stops being refreshed for an in-scope character that has the scope.
5. Any in-scope character drops out, or any out-of-scope character is added.
6. A newly added character takes longer to get its first fetch than it does today.
7. Affiliation runs overlap or take longer than 5 minutes.
8. An assignee on an open industry order goes more than 1.5 h without a jobs or contracts fetch.

Intended changes, for sign-off:
- Skills, clones, killmails, mining, planets and blueprints go from 4 h to 24 h.
- Contracts and jobs go to 1 h for open-order assignees.
- Affiliations go from 30 min to 15 min.
- Characters only ever assigned to closed orders stop getting the extra industry job fetch.
- `update_character` stops re-fetching public data.

## Phases

**Phase 0: measure (no code).**
- On `production_readonly`: in-scope characters per section scope, suspended count, and characters on open industry orders.
- `update_character` duration p50/p95, and which sections take the time.
- `Expires` on `/characters/affiliation/`.

**Phase 1: record only (no behavior change).**
- Add the model and the registry.
- `update_character`, `update_character_urgent`, `tech` and the tribes button call the registry in today's order and stamp each section.
- Add `character_sync_status`.
- After a day this is the baseline for checks 1, 6 and 8.
- Rollback: revert.

**Phase 2: shadow scheduler, plus affiliations.**
- Add the `CHARACTER_SYNC_MODE` setting (`fanout` | `shadow` | `scheduled`) in `app/settings_env.py`, the same way as `FRONTEND_GATE_SOURCE`, defaulting to `fanout`.
- In shadow mode, log each tick's batch for 2 days.
- Ship the 15-minute affiliation change and the bulk load on their own; they don't depend on the scheduler.

**Phase 3: flip.**
- Set `scheduled`. `update_alliance_characters` and `sync_industry_jobs_for_order_assignees` return early.
- Watch checks 1–8 for one week.
- Rollback: set the mode to `fanout` and restart workers and beat.

**Phase 4: cleanup (two weeks after the flip).**
- Remove `fanout` mode, `update_alliance_characters`, `sync_industry_jobs_for_order_assignees` and their beat entries, with a migration deleting their `PeriodicTask` rows.
- Move corporation history into the registry and delete `queue_stale_character_corporation_history` and its beat row the same way.
- Drop `rate_limit` from both tasks, and the public-data call and downtime self-requeue from `update_character`.
- Replace the cron monitor entry.

## Out of scope
- **ETags for character endpoints.** Fixing django-esi's 304 handling would make unchanged sections nearly free. Separate change.
- **Market orders, fleet implants and notifications.** They have their own audiences and pacing, and each already works.
- **Moving the bulk sync to its own queue.** Not needed once the scheduler keeps `eveonline` drained.

## Decided (2026-11-19)
- Applicants are fetched once, when they add their characters, and not again until they're in the alliance.
- Refresh intervals are set per section. Assets and sections that features depend on stay at 4 h, skills and similar go to 24 h, and affiliations go to about 15 min.
- Killmails and mining stay daily. A fleet activity job waits until something reads that data per fleet.

## Open decisions
1. The 1 h tier for open-order assignees: is "user has an open industry order assignment" the right audience?
2. Does "members" need to include anyone outside today's scope, for example users on leave?
