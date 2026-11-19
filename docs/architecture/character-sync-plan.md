# Character sync: a refresh interval per data type, paced by one scheduler

Status: plan, November 2026. Follows the #3110 deploy, where the `eveonline` queue was 1,608 deep and the notification poller starved behind it (fixed separately in #3111).

## Problem

`update_alliance_characters` runs at :37 every 4 hours and queues `update_character` for every character of every user who has a character in a tracked alliance. `update_character` refreshes every section (public data, assets, skills, killmails, contracts, industry jobs, mining, planets, blueprints, clones) every time, and is `rate_limit="5/m"`.

- **One interval for everything.** 4 hours was picked to fit most cases broadly. Skills, blueprints and mining don't need it; assets, contracts and industry jobs, which other features depend on, do. Affiliations are a separate task every 30 minutes, which is too slow for membership changes.
- **The pace depends on replica count.** Celery applies `rate_limit` per worker container. With 4 `celery-eveonline` replicas that's about 20 characters a minute, and scaling the service changes it silently.
- **The limit doesn't protect anything ESI enforces.** ESI limits a token bucket per route group per character, plus an app-wide budget of 100 error responses a minute (`eveonline/esi_budget.py`). A global calls-per-minute cap protects neither, and a few dead tokens can still burn the error budget.
- **The queue is backed up most of the time.** The 20:37 run on 2026-11-19 queued roughly 2,800 characters, an estimate from 1,608 still waiting after about an hour at about 20 a minute. That takes about 140 minutes to drain out of each 240-minute cycle. Past roughly 4,800 characters it never drains.
- **Everything else on `eveonline` waits behind it**: corporation syncs, structures, token work, a new character's first fetch, and until #3111 the notification poller.
- **The queue-health warning is noise.** The 30-minute Sentry warning fires every 4 hours during normal running, so a real backlog looks routine.
- **Downtime makes it worse.** During ESI downtime `update_character` re-queues itself with a countdown, so the whole pile shifts to 11:15 instead of being dropped.
- **Public data is fetched twice.** `update_character` calls `refresh_character_public_data`, which `update_all_character_public_data` already runs for every character every 8 hours.
- **Nothing records freshness**, so we can't tell how stale any character or section is.

## Goals: up to date, within reason

### Refresh interval per data type (members)

"Members" means today's scope: every character with a token belonging to a user who has a character in a tracked alliance. The "ESI cache" column is how long ESI serves the same answer; fetching more often than that returns nothing new.

| Section | What reads it | ESI cache | Today | Proposed |
| --- | --- | --- | --- | --- |
| Affiliations (bulk, every character) | Alliance scope itself, groups and Discord roles, application auto-accept | verify in Phase 0 | 30 min | **15 min** |
| Assets | Fleet ship pickers and hangars, industry, tribes (hull checks), tech | 1 h | 4 h | **4 h** |
| Contracts, plus industry contract reconcile | Industry order delivery, market | 5 min | 4 h | **4 h** |
| Industry jobs, plus "job detected" notifications | Industry orders | 5 min | 4 h | **4 h** |
| Skills, plus readiness re-rate | Capabilities and fleet readiness, Training tab, tribes, applications | 2 min | 4 h | **24 h** |
| Clones and implants | Industry, character pages | 2 min | 4 h | **24 h** |
| Killmails | Activity, timezones, tribes, applications, reports. Fleet fights read the zKill feed instead (see §6) | 5 min | 4 h | **24 h**, plus after a fleet (§6) |
| Mining ledger | Mining stats (alliance, tribes, industry); ESI keeps 30 days | 10 min | 4 h | **24 h**, plus after a fleet (§6) |
| Planets | Industry and PI | 10 min | 4 h | **24 h** |
| Blueprints | Industry | 1 h | 4 h | **24 h** |
| Public data (sec status, corp history) | Already refreshed by `update_all_character_public_data` | — | 4 h plus 8 h | **8 h**, separate task only |

The "What reads it" column comes from where each model is imported (`EveCharacterAsset`, `EveCharacterSkill`, ...). Confirm it per section before the flip.

Alert when more than 5% of a section's in-scope characters are older than twice its interval.

### Other characters (unchanged)

| Who | Target | Alert when |
| --- | --- | --- |
| A newly added character, including applicants | Every section once, within a minute of adding it (`update_character_urgent`) | Not synced 10 min after it was added |
| Applicants after that first fetch, and everyone else outside member scope | Not synced. Applicants join the member intervals when the affiliation sync puts them in a tracked alliance. | — |

Characters that are `esi_deleted` or `esi_suspended` stay skipped. `tech` manual refreshes still run every section on demand.

### ESI load
- **Today:** about 2,800 characters × 6 syncs a day × 10 sections, roughly 168,000 section fetches a day.
- **Proposed:** 3 sections every 4 h and 6 sections daily is 24 fetches per character a day, roughly 67,000 a day, about 60% fewer.
- **Affiliations at 15 min:** about 3 bulk calls per run (1,000 characters each), so negligible.

## Design

### 1. Record freshness per section
New model `EveCharacterSyncState`:
- **Fields:** `character` (FK), `section`, `attempted_at`, `synced_at`, `last_error`.
- **Constraints:** unique on (`character`, `section`), index on (`section`, `attempted_at`).
- **Why a table:** a row per section keeps `EveCharacter` free of 18 timestamp fields, and adding a section later needs no migration.

### 2. A section registry
`eveonline/character_sync.py` lists every section with:
- its name;
- the token scope(s) it needs (the same checks `update_character` does with `Token.get_token` today);
- its refresh function, including the follow-ups it triggers today (contract reconcile, job notifications, readiness re-rate);
- its interval, from the table above.

These are the only place intervals are set. Changing one is a one-line PR.

### 3. One scheduler sets the pace
`eveonline.tasks.characters.queue_due_character_syncs` runs every 5 minutes.

Each tick:
1. For each section, finds in-scope characters that have the scope and whose `attempted_at` is older than the section's interval, or that have no row yet.
2. Groups them by character, so one task covers all of a character's due sections.
3. Orders by most overdue relative to the interval, with never-synced first.
4. Takes characters until it reaches `CHARACTER_SYNC_SECTIONS_PER_TICK` section fetches (default 300; the steady state is about 235).
5. Queues `sync_character_sections(character_id, sections)` with countdowns spread across the 5 minutes.

Properties:
- **A missed tick costs nothing.** Tracking is by timestamp, so the next tick picks up the same characters.
- **No 4-hourly spike.** On first rollout, everything is due at once, but the budget spreads the backlog, and from then on it stays spread.

### 4. A sync task without a Celery rate limit
`sync_character_sections(character_id, sections)` runs the registry functions for the given sections, in today's order, and stamps each section.

- **ESI downtime:** it returns without re-queuing, and the next tick after 11:15 picks the character up.
- **Error budget:** before each section it checks `esi_budget.error_budget()`. Below the floor it stops without stamping the remaining sections, so they stay due.
- **Error-limit abort:** an `ESIErrorLimitException` stamps the attempt for that section only, so a broken token waits a full interval instead of being retried every tick.

`update_character` keeps its `rate_limit` until cleanup, so rolling back to the old fan-out stays safe.

### 5. Affiliations every 15 minutes
- Change the beat entry from `minute="0,30"` to every 15 minutes, with `expire_seconds` set to 15 minutes.
- Load characters in bulk instead of doing a `.get()` per result, so the run stays short as the character count grows.
- If Phase 0 shows ESI caches affiliations for an hour, 15 minutes only helps for ESI's cache boundary. Raise that with you before switching.

### 6. Fleet activity sync
Killmails and mining matter right after a fleet, not on a daily cycle, so they get a fleet-driven job instead of a shorter interval for everyone.

- **Fleet fights are already covered.** They don't read character killmails: the fight timeline uses the live zKill feed, `sweep_fight_killmails` fills gaps from zKill, and `settle_fight_timeline` closes it. Nothing about fight reports changes.
- **The new job:** `sync_fleet_participant_activity(fleet_id)` queues `sync_character_sections(character_id, ["killmails", "mining"])` for the characters that flew. It skips characters whose sections synced in the last 30 minutes.
- **When it runs:** queued from `settle_fight_timeline`, so it runs once per fleet, after the fight is over.
- **Mining fleets:** run it a second time about 1 hour after the fleet ends, because the mining ledger lags and ESI caches it for 10 minutes. Nothing reads mining per fleet today, so this only matters for activity stats or a future mining-fleet view.
- **Fleet tracking isn't affected.** It uses its own `fleet` ESI group and the `fleets` queue. The participant syncs run on `eveonline` and count against the same per-tick budget, so a big fleet can't flood ESI.

### 7. New characters stay immediate
`update_character_urgent` keeps running every section when a token is added, applicants included, and stamps every section. With `eveonline` drained every tick, it runs within about a minute instead of waiting behind the fan-out.

### 8. Visibility
- **Status command:** `manage.py character_sync_status` prints, per section, the in-scope count, overdue count, p95 age and oldest age. It also lists characters added in the last day with no synced sections.
- **Sentry check:** a check beside `monitor_queue_health` warns on the alert thresholds above.
- **Cron monitor:** the scheduler gets a Sentry cron monitor (`CRON_MONITORED_SCHEDULES`). The old fan-out's entry goes at cleanup.
- **Queue limit:** `eveonline`'s 30-minute warning stays. With the queue drained every tick, a warning now means a real problem.

## What counts as a regression

Each item below is checked with `character_sync_status` and Sentry before the next phase:

1. A section's p99 age goes above 1.5 × its interval. For the 4 h sections that's 6 h, which is still better than today's worst case of about 6.5 h.
2. Total ESI calls per hour rise.
3. ESI error-budget dips (`esi_budget.snapshot()`) or 420s become more frequent.
4. A section stops being refreshed for an in-scope character that has the scope.
5. Any in-scope character drops out, or any out-of-scope character is added.
6. A newly added character takes longer to get its first fetch than it does today.
7. Affiliation runs overlap or take longer than 5 minutes.
8. A settled fleet's participants still have killmail or mining data older than the fleet's end 2 hours after it settles.

Intended changes, for sign-off:
- Skills, clones, killmails, mining, planets and blueprints go from 4 h to 24 h.
- Affiliations go from 30 min to 15 min.
- `update_character` stops re-fetching public data (still every 8 h).

## Phases

**Phase 0: measure (no code).**
- On the `production_readonly` alias: in-scope characters per section scope, and the suspended count.
- `update_character` duration p50/p95, and which sections take the time.
- The ESI cache time (`Expires`) on `/characters/affiliation/`.

These confirm the budget and the affiliation interval.

**Phase 1: record only (no behavior change).**
- Add the model and the registry.
- `update_character` and `update_character_urgent` call the registry functions in today's order and stamp each section.
- Add `character_sync_status`.
- The fan-out and intervals are unchanged. After a day the status command shows today's real staleness per section, which is the baseline for checks 1 and 6.
- Rollback: revert; the table is unused.

**Phase 2: shadow scheduler, plus affiliations.**
- Add a `CHARACTER_SYNC_MODE` setting (`fanout` | `shadow` | `scheduled`), set from `app/settings_env.py` the same way as `FRONTEND_GATE_SOURCE`, defaulting to `fanout`.
- In `shadow` mode the scheduler logs each tick's batch (characters, sections, fetches, oldest age) but queues nothing. Run it for 2 days.
- Ship the 15-minute affiliation change on its own here; it doesn't depend on the scheduler. Rollback: revert the beat entry, plus a beat restart.

**Phase 3: flip.**
- Set `CHARACTER_SYNC_MODE=scheduled`. The scheduler queues `sync_character_sections`, and `update_alliance_characters` returns early.
- Turn on the fleet activity sync (§6) from `settle_fight_timeline`.
- Watch checks 1–6 and 8 for one week.
- Rollback: set the mode to `fanout` and restart workers and beat.

**Phase 4: cleanup (two weeks after the flip).**
- Remove `fanout` mode, `update_alliance_characters` and its beat entry, with a migration that deletes its stale `PeriodicTask` row.
- Remove the old cron monitor entry.
- Drop `rate_limit` and the public-data call from `update_character`, or make it call the new task for every section.
- Remove the self-requeue during downtime.

## Out of scope
- **ETags for character endpoints.** `eveonline/client.py` disables them because django-esi raises on 304. Fixing that would make 4 h sections almost free when nothing changed. Separate change.
- **More event-driven refreshes**, such as refreshing assets when an industry order is delivered. §6 is the first one; the registry makes others an urgent sync for the sections involved.
- **Moving the bulk sync to its own queue.** Not needed once the scheduler keeps `eveonline` drained. Revisit if Phase 3 shows contention.

## Decided
- Applicants are fetched once, when they add their characters, and not again until they're in the alliance (2026-11-19).
- Refresh intervals are set per section, not one interval for everything. Assets and other sections that features depend on stay at 4 h, skills and similar go to 24 h, and affiliations go to about 15 min (2026-11-19).
- Killmails and mining stay daily, plus a fleet activity sync for the characters that flew (2026-11-19).

## Open decisions
1. Contracts and industry jobs: 4 h, or faster? ESI caches them for 5 min, and industry delivery and "job detected" notifications depend on them. 1 h for both would add about 100,800 fetches a day (2,800 characters × 18 extra × 2 sections), back to roughly today's total.
2. Skills at 24 h: is daily enough for fleet readiness? If a pilot finishes a skill and wants it to count before tonight's fleet, the only refresh today is an admin `tech` refresh. Should pilots get a "refresh my characters" button, limited to once an hour?
3. Does "members" need to include anyone outside today's scope, for example users on leave?
