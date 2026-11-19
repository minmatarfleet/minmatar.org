# Character sync: a refresh interval per data type, paced by one scheduler

Status: plan, November 2026, checked against `main` at `ed22fbc5c`, revised after an architecture review and a code review. Follows the #3110 deploy, where the `eveonline` queue was 1,608 deep and the notification poller starved behind it (fixed separately in #3111).

## What exists today

Several jobs already pull character data, each with its own cadence, audience and pacing.

| Job | Schedule | Audience | What it fetches | Pacing |
| --- | --- | --- | --- | --- |
| `update_alliance_characters` → `update_character` | :37 every 4 h | Every character of every user with a character in a tracked alliance, with a token, not `esi_deleted` | Public data, assets, skills (+ readiness re-rate), killmails, contracts (+ industry reconcile), industry jobs (+ job notifications), mining, planets, blueprints, clones+implants | `rate_limit="5/m"` per worker container |
| `update_character_urgent` (`eveonline/signals.py`) | When an `EveCharacter` is created with a token | That character | Same as above | None (calls the function inline) |
| `tech` router | Admin action | One user's characters | Same as above | None |
| `tribes…post_membership_characters_available_refresh` | Pilot button | One character | Assets and skills, inline; returns the rebuilt schema | 1 h cooldown per character (cache key) |
| `update_all_character_public_data` | :20 every 8 h | Every character not `esi_deleted` | Public data (also sets `esi_deleted` and triggers corp history on a corp change) | One long task, inline loop |
| `queue_stale_character_corporation_history` → `sync_character_corporation_history_task` | :05 and :35 | 50 characters per run with stale `corporation_history_synced_at` (24 h TTL) | Corporation history | Stamp + stale batch, `rate_limit="10/m"` |
| `update_character_affilliations` | :00 and :30 | Every `EveCharacter` | Affiliations, bulk, 1,000 per call | One task; per-result `.get()`; queues `groups.update_affiliation` per changed user |
| `groups.update_affiliations` / `applications.accept_applications_of_members_task` | :15 and :45 | Every user / pending applicants | Nothing from ESI; full reconcile sweeps | — |
| `industry.sync_industry_jobs_for_order_assignees` → `sync_industry_jobs_for_character` | :05 every 4 h, `industry` queue | Every character ever assigned to an order item, plus their user's other characters, in any alliance | Industry jobs (+ job notifications) | `cooldown` 1 h |
| `industry.reconcile_industry_contract_associations_task` | :35 every 2 h | — | Nothing from ESI; matches the order *owner's* stored contracts to open orders | — |
| `update_corporations` → `update_corporation` | :00 hourly, `eveonline` queue | Every tracked corporation | Corporation data including corp contracts. Freight reads these: `FreightContract` is a filtered view of `EveCorporationContract` for corp 98705678 | `rate_limit="10/m"` |
| `buyback.sync_buyback_ledger_task` | :25 hourly | The buyback corporation (M-EXC) | Corp contracts in and out, plus a corp hangar asset snapshot | One task |
| `campaigns.poll_campaign_recent_killmails` | 30 min | Enlisted campaign characters | Recent killmails missing from `FeedKillmail`, into the feed | `esi_budget` `char-killmail` bucket |
| `market.fetch_attributed_market_orders` | 30 min | Market-scoped characters of eligible tribe members | Character market orders | Per-character tasks |
| `fleets.poll_active_fleet_implants` | 10 min | Members of qualifying live fleets (`members_to_poll`) | Implant snapshots | Spread with countdowns |
| `eveonline.tasks.notifications` | Every minute, a tenth of the roster | Characters with the notification scope | Notifications | Minute buckets (`character_id % 10`), `esi_budget` |

Facts that shape the design:
- **Two stamps already exist:** `EveCharacter.clones_synced_at`, written only by the clones helper, and `corporation_history_synced_at`. The corporation-history job already works the way this plan proposes (stamp, then sync a stale batch), at small scale.
- **Section helpers swallow failures.** They log and return 0 or None (`eveonline/helpers/characters/update.py`). `EsiClient` turns `ESIErrorLimitException` into a 420 response instead of raising (`eveonline/client.py`). Today nothing can tell "synced" from "failed".
- **The error-budget ledger only sees part of our traffic.** `esi_http` routes (planets, clones, killmails by hash, notifications) report to `esi_budget`. django-esi operations (assets, skills, contracts, jobs, mining, blueprints, recent killmails) never call `observe_response`.
- **Token buckets are per character.** `char-killmail` is 30 tokens per character per 15 minutes. A daily killmail sync and the campaigns poll can't starve each other.
- **ETags are off** for character endpoints (django-esi raises on 304), so every sync is a full fetch.
- **Four tasks on `eveonline` use `rate_limit`:** `update_character` (5/m), `sync_character_corporation_history_task` (10/m), `update_corporation` (10/m) and `sync_corporation_projects` (20/m). `.claude/rules/celery-tasks.md` says to use `esi_budget` instead.
- **Contracts only matter for order owners.** Reconcile reads contracts stored under the order owner (`industry/helpers/contract_associations.py`, `candidate_contracts_for_order`). Yet every contracts sync queues a reconcile for the character, whether or not it owns an open order.
- **Industry jobs are fetched twice** for most assignees. The industry job's audience is every character ever assigned, including those on closed orders, and it isn't limited to members.
- **`EveCharacter.alliance_id` has no index.**
- **Buyback and freight read corporation data, not character data.** Buyback reads M-EXC's corp contracts and corp assets (`buyback/helpers/contracts_ledger.py`, `hangar.py`). Freight reads the freight corporation's corp contracts. Both refresh hourly. Freight's refresh sits behind the `eveonline` backlog, and behind `update_corporation`'s rate limit.
- **The live-fleet window already exists for implants.** `fleets.helpers.active_clones` polls members of fleets started in the last 45 minutes, every 10 minutes.

## Problem

- **One interval for everything.** 4 hours was picked to fit most cases broadly. Skills, blueprints and mining don't need it; assets, contracts and industry jobs, which other features depend on, do.
- **The pace depends on replica count.** `rate_limit` is per worker container: 4 `celery-eveonline` replicas means about 20 characters a minute.
- **The queue is backed up most of the time.** The 20:37 run on 2026-11-19 queued roughly 2,800 characters, an estimate from 1,608 still waiting after about an hour. That takes about 140 minutes to drain out of each 240-minute cycle. Past roughly 4,800 characters it never drains.
- **Everything else on `eveonline` waits behind it**, including a new character's first fetch (applicants included).
- **The queue-health warning is noise.** It fires every 4 hours during normal running.
- **Downtime makes it worse.** `update_character` re-queues itself during ESI downtime, which `.claude/rules/celery-tasks.md` forbids. The pile moves to 11:15.
- **Nothing records freshness or failure**, and overlapping jobs fetch the same data on separate schedules.

## Goals: up to date, within reason

### Refresh interval per section (members)

"Members" keeps today's scope. ESI cache is how long ESI serves the same answer; fetching more often than that returns nothing new.

| Section | What reads it | ESI cache | Today | Proposed |
| --- | --- | --- | --- | --- |
| Affiliations (bulk, every character) | Alliance scope, groups and Discord roles, application auto-accept | verify in Phase 0 | 30 min | **15 min** |
| Assets | Fleet ship pickers and hangars, industry, tribes (hull checks), tech | 1 h | 4 h | **4 h**. Buyback reads the M-EXC corp hangar, which has its own sync (§10) |
| Contracts | Industry order delivery (reconciled every 2 h), market | 5 min | 4 h | **4 h**; **1 h** for characters that own an open industry order. Freight and buyback read corp contracts, which have their own sync (§10) |
| Industry jobs, plus "job detected" notifications | Industry orders | 5 min | 4 h, twice | **4 h**; **1 h** for characters with an undelivered assignment on an open order, plus their user's other characters. Replaces `sync_industry_jobs_for_order_assignees` |
| Skills, plus readiness re-rate | Capabilities and fleet readiness, Training tab, tribes, applications | 2 min | 4 h | **24 h**, plus the pilot refresh button |
| Clones and implants | Industry, character pages (fleets poll implants live separately) | 2 min | 4 h | **24 h** |
| Killmails | Activity, timezones, tribes, applications, reports. Fleet fights use the zKill feed; campaigns poll enlisted characters every 30 min | 5 min | 4 h | **24 h**; **15 min** while the character is on an active fleet (§7) |
| Mining ledger | Mining stats (alliance, tribes, industry); ESI keeps 30 days | 10 min | 4 h | **24 h**; **15 min** while the character is on an active fleet (§7) |
| Planets | Industry and PI | 10 min | 4 h | **72 h** for members of the Planetary Interaction tribe group (`supply.planetary-interaction`); **weekly** for everyone else |
| Blueprints | Industry | 1 h | 4 h | **24 h** |
| Corporation history | Corp pages, applications | — | 24 h TTL (own job) | **24 h**, moved into the registry |
| Public data | Sec status, `esi_deleted`, corp-change trigger | — | 4 h plus 8 h | **8 h**, own task only |

- **Industry audiences:** the 1 h audiences are in scope even when the character isn't a member, as the industry job covers today.
- **Confirm before the flip:** the "What reads it" column comes from where each model is imported.
- **Alert** when more than 5% of a section's in-scope characters have `synced_at` older than twice the interval.

### Other characters (unchanged)

| Who | Target | Alert when |
| --- | --- | --- |
| A newly added character, applicants included | Every section once, within a minute (`update_character_urgent`), retried if it fails | Not synced 10 min after it was added |
| Applicants after that, and everyone else outside member scope | Not synced. Applicants join the member intervals when the affiliation sync puts them in a tracked alliance. | — |

`esi_deleted` and `esi_suspended` characters stay skipped. `tech` and the tribes refresh button keep working on demand.

### ESI load
- **Today:** about 2,800 characters × 6 syncs a day × 10 sections, plus the industry job's duplicate fetches. Roughly 170,000 section fetches a day.
- **Proposed:** 3 sections every 4 h plus 5 daily, with planets at 72 h or weekly, is about 23 fetches a day per character, roughly 64,000 a day.
- **The 1 h industry audiences** add 18 fetches a day for each character in them; measure their size in Phase 0.
- **Active fleets** add killmails and mining every 15 minutes for each pilot while the fleet runs: a 40-pilot, 2-hour fleet is about 640 fetches.
- **Not all sections cost the same.** Assets and blueprints are paged, and killmails fetch one detail per new mail. The per-tick budget weights them (§3).

## Design

### 1. Sections report a result
Phase 2 changes each section helper to return a result instead of swallowing it:
- `ok`
- `no_scope`
- `suspended`
- `error` with an HTTP status: 420 for the error limit, 5xx, or 4xx

`EsiClient` reports every django-esi response's status and error-limit headers to `esi_budget.observe_response`, in one place. Then the error-budget ledger sees all of our traffic.

Callers that ignore the return value keep working.

### 2. Record freshness per section
New model `EveCharacterSyncState`:
- **Fields:** `character` FK, `section`, `next_due_at`, `queued_at`, `attempted_at`, `synced_at`, `last_error`, `consecutive_failures`.
- **Constraints:** unique on (`character`, `section`), index on (`section`, `next_due_at`).

Stamping, per section, when the call returns:

| Result | Stamp |
| --- | --- |
| `ok` | `synced_at` = now. `next_due_at` = now + interval × random(0.9–1.1), so sections spread out instead of falling due together. `consecutive_failures` = 0. |
| `no_scope`, `suspended` | `next_due_at` = now + interval |
| 4xx (broken token, forbidden) | `last_error`, `consecutive_failures` + 1. `next_due_at` = now + 30 min, or the full interval after 3 failures in a row. |
| 420, 5xx, budget paused | Nothing. The task stops and every remaining section stays due. |

The interval is worked out when the row is stamped, using the 1 h industry audiences, so the scheduler only compares `next_due_at` with now.

When an assignment is created, or an order is opened or fulfilled, the affected characters' contracts and jobs `next_due_at` moves to now. A newly assigned character doesn't wait 4 h.

Existing stamps: `corporation_history_synced_at` stays until corporation history moves into the registry in Phase 5; `clones_synced_at` stays; nothing else reads it.

### 3. A section registry and one scheduler
`eveonline/character_sync.py` lists each section with:
- its name and required token scopes (the `SCOPE_*` constants);
- its refresh function, including today's follow-ups (job notifications, readiness re-rate);
- its intervals and audiences;
- its cost weight (assets and blueprints count 3, others 1, adjusted with Phase 0 timings).

The contracts follow-up queues a reconcile only when the character owns an open order, per the "fan out only work that will run" rule.

`queue_due_character_syncs` runs every 5 minutes. The beat entry sets `"options": {"expire_seconds": 5 * 60}`.

Each tick:
1. Skips the whole tick during ESI downtime (`get_esi_downtime_countdown() > 0`) or a paused budget (`esi_budget.pause_remaining(None) > 0`).
2. Works out the in-scope character IDs once: members plus the 1 h industry audiences, with a token, not `esi_deleted` or `esi_suspended`. Phase 2 adds an index on `alliance_id`.
3. Loads (character, scope) pairs with one query on token scopes, not one `Token.get_token` call per pair.
4. Selects due rows: `next_due_at <= now`, `queued_at` null or older than 15 min, ordered by `next_due_at`. Characters with a token that have never synced count too, whatever their scope, so a first fetch lost to downtime or an error is retried.
5. Groups rows by character and takes characters until the weighted budget `CHARACTER_SYNC_COST_PER_TICK` is reached. The default is set in Phase 0, from about 235 unweighted section fetches per tick at steady state.
6. Stamps `queued_at` in the same UPDATE, then queues `sync_character_sections(character_id)` with countdowns spread across the 5 minutes.

### 4. The sync task
`sync_character_sections(character_id)`:
- **Options:** `expires=10 * 60`, `exclusive` per character (urgent, `tech` and scheduled runs never overlap), and no Celery `rate_limit`.
- **Argument:** it takes only the character id. AppTask dedupe drops a second copy, and the task works out which sections are due when it runs.
- **Order:** it runs due sections in today's order and stamps each one as it returns. A rolling deploy that kills it mid-run loses only the section in progress; that section's `next_due_at` hasn't moved, so it stays due.
- **Error budget:** before each section it checks `esi_budget.error_budget()` (which now sees django-esi traffic) and stops below the floor.
- **Downtime:** it returns without re-queuing and without stamping.

### 5. Affiliations every 15 minutes
- **Schedule:** the beat entry moves from `minute="0,30"` to every 15 minutes, with `expire_seconds` set to 15 minutes.
- **Bulk loading:** characters are loaded in bulk instead of one `.get()` per result. The task covers every `EveCharacter`.
- **Effect:** changed users are already queued for `groups.update_affiliation` immediately, so membership changes reach groups and Discord within about 15 minutes. The :15/:45 sweeps stay as safety nets.
- **ESI cache:** if Phase 0 shows ESI caches affiliations for an hour, 15 minutes mostly re-reads the cache. Decide with that number in hand.

### 6. Pilot refresh button stays inline
The tribes endpoint returns the rebuilt schema from the fresh data, so it stays synchronous. It calls the registry's assets and skills functions inline and stamps them, with the same 1 h cooldown. This is the escape hatch for daily skills.

### 7. Killmails and mining while on a fleet
Killmails and mining get a third audience, "on an active fleet", with a 15-minute interval:
- **Who:** characters of `EveFleetInstanceMember` rows whose `EveFleetInstance` has no `end_time`, plus 30 minutes after it ends to catch late mails and ledger entries. Unlike implants, there's no 45-minute cutoff from the start; the whole fleet counts.
- **Why 15 minutes:** ESI caches killmails for 5 minutes and the mining ledger for 10, so 15 sits inside the 10–30 minute range and doesn't re-read the cache.
- **How:** joining a fleet sets both sections' `next_due_at` to now + 15 min. The interval is worked out when each row is stamped (§2), so the scheduler needs no special case. After the fleet's 30-minute tail ends, the next stamp goes back to the daily interval.
- **Fleet fights aren't affected.** They keep using the zKill feed. This keeps activity, mining and tribe stats current during and right after fleets.

### 8. New characters stay immediate
`update_character_urgent` sets every section's `next_due_at` to now and runs `sync_character_sections` with a 30-second countdown. With `eveonline` drained it runs within about a minute. If ESI is down or a section fails, the never-synced rule in §3 retries it. Public data still comes from the `EveCharacter` creation signal.

### 9. Visibility
- **Status command:** `manage.py character_sync_status` prints, per section, the in-scope count, overdue count, p95 and oldest `synced_at` age, and the failing count with the top `last_error` values. It also lists characters added in the last day with nothing synced.
- **Per-tick log:** each tick logs, per section, the number due against the budget. Saturation shows up before the age alert fires.
- **Sentry:** a check beside `monitor_queue_health` warns on the alert thresholds above.
- **Cron monitor:** the scheduler replaces `"[Characters] Update Characters (assets, skills, killmails)"` in `CRON_MONITORED_SCHEDULES` (`app/monitoring.py`).
- **Queue limit:** `eveonline`'s 30-minute warning stays and means something again.

### 10. Corporation contracts and assets for freight and buyback
These are corporation reads, outside the per-character registry. They get their own small task, `sync_service_corporations`, with its own beat entry every 10 minutes:
- **Freight:** the freight corporation's contracts (`update_corporation_contracts(98705678)`), every 10 minutes. ESI caches corp contracts for 5 minutes. This takes freight out of `update_corporation`'s hourly, rate-limited fan-out on the backed-up `eveonline` queue.
- **Buyback contracts:** M-EXC's contracts and the buyback contract ledger, every 10 minutes instead of hourly (`sync_buyback_ledger_task`).
- **Buyback assets:** the M-EXC corp hangar snapshot can't usefully go faster than hourly, because ESI caches corporation assets for 1 hour. It stays hourly, aligned to the cache expiry. Fresher stock between snapshots has to come from contracts and sell fills, which the ledger already tracks.
- **Load:** a handful of calls each run, on the `industry` queue for buyback and `eveonline` for freight.

## What counts as a regression

Checked with `character_sync_status` and Sentry before each phase. Ages are measured from `synced_at`:

1. A section's p99 age goes above 1.5 × its interval.
2. Total ESI calls per hour rise.
3. ESI error-budget dips (`esi_budget.snapshot()`) or 420s become more frequent.
4. A section stops being refreshed for an in-scope character that has the scope.
5. Any in-scope character drops out, or any out-of-scope character is added beyond the industry audiences already covered today.
6. A newly added character takes longer to get its first fetch than it does today.
7. Affiliation runs overlap or take longer than 5 minutes.
8. An open-order owner goes more than 1.5 h without a contracts fetch, or an assignee without a jobs fetch.
9. Freight or buyback corp contracts go more than 20 minutes without a sync.
10. A pilot on an active fleet goes more than 30 minutes without a killmail or mining fetch.

Intended changes, for sign-off:
- Skills, clones, killmails, mining and blueprints go from 4 h to 24 h. Planets go to 72 h for the PI group and weekly for everyone else.
- Killmails and mining go to 15 minutes for pilots on an active fleet.
- Freight and buyback corp contracts go from hourly to every 10 minutes.
- Contracts go to 1 h for open-order owners, and jobs to 1 h for assignees with undelivered work.
- Affiliations go from 30 min to 15 min.
- Characters only ever assigned to closed orders lose the extra 4-hourly jobs fetch.
- Industry jobs for non-member assignees move from the `industry` queue to `eveonline`.
- `update_character` stops re-fetching public data.

## Phases

**Phase 0: measure (no code).**
- On `production_readonly`: in-scope characters per section scope, suspended count, open-order owners and undelivered assignees.
- `update_character` duration p50/p95, and the time per section.
- `Expires` on `/characters/affiliation/`.
- These set the budget, the cost weights and the affiliation interval.

**Phase 1: quick relief (small, ships first).** This fixes the backlog before the bigger build:
- Drop `rate_limit` from `update_character`.
- Spread the fan-out over the 4 hours: a countdown from a hash of `character_id`, in 5-minute slots.
- Set `expires` to about 4 h.
- Replace the downtime self-requeue with a plain return.

The cadence and audience stay the same: every member every 4 h. Check that ESI calls per hour stay flat and error-budget dips don't rise. Rollback: revert.

**Phase 1b: freight and buyback contracts (small, ships with Phase 1).** Add `sync_service_corporations` every 10 minutes (§10). This doesn't depend on the scheduler. Rollback: remove the beat entry.

**Phase 2: results and freshness (no cadence or audience change).**
- Section helpers return results.
- `EsiClient` reports to `esi_budget`.
- Add the `alliance_id` index, the model and the registry.
- `update_character`, the urgent path, `tech` and the tribes button go through the registry and stamp rows.
- Add `character_sync_status`.
- Not yet: killmail budget spending and the tribes readiness re-rate, so the ESI calls made don't change.
- After a day this is the baseline for checks 1, 6 and 8.

**Phase 3: shadow scheduler, plus affiliations.**
- Add the `CHARACTER_SYNC_MODE` setting (`fanout` | `shadow` | `scheduled`), read from the environment in `app/settings_common.py` the same way as `FRONTEND_GATE_SOURCE`, defaulting to `fanout`. Changing it needs a restart.
- In shadow mode, log each tick's batch and costs for 2 days.
- Ship the 15-minute affiliation change and the bulk load on their own.

**Phase 4: flip.**
- Run a one-off command that spreads every section's `next_due_at` evenly across its interval, so the first day isn't one spike.
- Set `scheduled`. `update_alliance_characters` and `sync_industry_jobs_for_order_assignees` return early. Turn on the industry triggers that move `next_due_at` (§2).
- Watch checks 1–10 for one week.
- Rollback: set the mode to `fanout` and restart. Already-queued scheduler messages still run once, which is harmless.

**Phase 5: cleanup (two weeks after the flip).**
- Remove `fanout` mode, `update_alliance_characters`, `sync_industry_jobs_for_order_assignees` and their beat entries, with a migration deleting their `PeriodicTask` rows.
- Move corporation history into the registry. Remove `queue_stale_character_corporation_history`, its `rate_limit` task and its beat row the same way.
- Drop the public-data call from `update_character`.
- `update_corporation` and `sync_corporation_projects` keep their `rate_limit`. Moving them to `esi_budget` is a separate change.

## Out of scope
- **ETags for character endpoints.** Fixing django-esi's 304 handling would make unchanged sections nearly free. Separate change.
- **Market orders, fleet implants and notifications.** They have their own audiences and pacing, and each already works.
- **Moving the bulk sync to its own queue.** Not needed once the scheduler keeps `eveonline` drained.

## Decided (2026-11-19)
- Applicants are fetched once, when they add their characters, and not again until they're in the alliance.
- Refresh intervals are set per section. Assets and sections that features depend on stay at 4 h, skills and similar go to 24 h, and affiliations go to about 15 min.
- Killmails and mining are daily, and every 15 minutes while the pilot is on an active fleet.
- Planets are 72 h for the PI tribe group and weekly for everyone else.
- Freight and buyback corporation contracts refresh every 10–15 minutes. Buyback corp assets stay hourly, the ESI cache floor.

## Open decisions
1. Does "members" need to include anyone outside today's scope, for example users on leave?
2. Can the 1 h jobs tier for assignees' other characters be dropped? Jobs run on whichever character the pilot builds with, so probably not.
