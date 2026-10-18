# Killmail feed and rollups

The `feed` app (`backend/feed/`) records every non-NPC killmail in the systems we watch and turns them into feed cards (rollups). Campaigns, the fleet kill feed, the warzone briefing, capital and Amarr fleet pings, and the desktop Intel window all read from it. This page describes how a killmail gets in, what happens to it, and how to add a rollup.

## Monitored systems

Only killmails in an active `FeedMonitoredSystem` are kept. `source` says why a system is watched:

| Source | Added by |
| --- | --- |
| `fw_warzone` | `seed_feed_monitored_systems` (the Amarr–Minmatar warzone) |
| `manual` | An admin, in Django admin |
| `campaign` | A campaign growing its theater (`backend/campaigns/services/structures.py`) |

`feed/helpers/monitored_systems.py` caches the active ids per process for 5 minutes (`CACHE_TTL_SECONDS`). Saving or deleting a row clears the cache in that process (`feed/apps.py`); other workers pick the change up within 5 minutes.

## How a killmail gets in

```text
zKill R2Z2 stream ──> poll_zkill_r2z2 (every 7 s) ──> upsert_feed_killmail_from_r2z2
                                                         │ discard: NPC kill, unmonitored system,
                                                         │          no id/hash/time
                                                         ├─> FeedKillmail (update_or_create on killmail_id)
                                                         ├─> FeedCharacterAffiliation (from the mail)
                                                         └─> campaigns.services.attribution.attribute_feed_killmail
```

- **Live stream.** `feed.tasks.poll_zkill_r2z2` (every 15 seconds on the `feed` queue, never two at once; see [celery-queues.md](celery-queues.md)) reads zKillboard's R2Z2 sequence through `feed/helpers/r2z2.py`, keeping its place in `FeedR2z2Cursor`. The same loop sends capital kill pings (`feed/helpers/capital_pings.py`).
- **Every path goes through one function.** `feed/helpers/ingest.py` `upsert_feed_killmail_from_r2z2` (or `upsert_feed_killmail_from_raw` for an ESI-shaped mail) is used by the stream and by the backfill commands (`backfill_feed_killmails`, `backfill_engagement`, `import_feed_killmail`). Never write `FeedKillmail` rows another way: campaign attribution is hooked in here, and campaigns have no other backfill.
- **Campaign hook.** After the row is saved, the mail is handed to `attribute_feed_killmail`. A failure there is logged and swallowed so the feed keeps recording; `campaigns.tasks.sweep_campaign_killmails` re-attributes the last 48 hours. The import is inside the function on purpose: campaigns depend on the feed, not the other way round.
- **Retention.** `purge_feed_killmails` (daily, 04:30) deletes `FeedKillmail` rows older than `FEED_KILLMAIL_RETENTION_DAYS` (30). Anything that needs a mail for longer copies what it needs (campaigns keep their own `CampaignKillmail` rows).

Other scheduled feed tasks (`app/settings_celery.py`): `detect_feed_clusters` and `run_feed_rollups` every 3 minutes over the last 48 hours, `populate_feed_affiliations` every 3 minutes and `refresh_feed_affiliations` every 6 hours (pilot militia and alliance from ESI), and `poll_fw_contested_snapshots` hourly (`FeedSystemContestedSnapshot`).

## Rollups

A rollup reads stored rows and writes `FeedEvent` cards. `feed.tasks.run_feed_rollups` builds one `RollupContext` (the window, each rollup's config, system names), runs the processors, and `feed/rollups/writer.py` upserts the events with their `FeedEventKillmailLink` / `FeedEventFleetLink` rows. Each pass rewrites the same event (keyed by `cluster_key`, or `source_type` + `source_id`), so a card grows while the fight goes on.

| Code | Processor | Card |
| --- | --- | --- |
| `kill_burst` | `feed/rollups/kill_burst.py` | `killmail_batch`: many kills in one system in a short window |
| `fleet_active` | `feed/rollups/fleet_active.py` | A fleet-sized engagement, sized by tier (`engagement_copy`). An Amarr-accented card also sends the Amarr fleet ping (`feed/helpers/amarr_fleet_pings.py`) |
| `fleet_kills` | `feed/rollups/fleet_kills.py` | One card per tracked fleet instance: what it killed and lost. The fleet results and history pages read it through `FeedEventFleetLink` (`fleets/endpoints/metrics/get_fleet_results.py`) |

Thresholds live in `DEFAULT_ROLLUP_CONFIG` (`feed/constants.py`) and can be overridden per rollup in Django admin (`FeedRollupConfig.config`, merged over the defaults; `is_enabled` turns a rollup off). `rebuild_feed_rollups` re-runs them over a longer window.

### Adding a rollup

1. Write `feed/rollups/<code>.py` with a `run_<code>_rollup(ctx: RollupContext) -> list[RollupResult]`. Read stored rows only; a rollup must not call ESI or zKill.
2. Register it in `ROLLUP_PROCESSORS` (`feed/rollups/registry.py`) **and** add the code to the list `run_feed_rollups` passes in `feed/tasks.py`; the task runs only the codes it names.
3. Add its defaults to `DEFAULT_ROLLUP_CONFIG` and its version to `ROLLUP_VERSIONS` (`feed/constants.py`). Bump the version when the card's shape changes.
4. If it is a new kind of card, add it to `FeedEvent.Kind` (a migration) and teach the feed page to render it.
5. Give every result a stable key (`cluster_key`, or `source_type` + `source_id`) so later passes update the same event instead of adding new ones.
6. Test it against stored `FeedKillmail` rows; tests can't reach zKill (`NetworkAccessBlocked`).

## Who reads the feed

| Reader | What it uses |
| --- | --- |
| Campaigns (`backend/campaigns/`) | Ingest hook, `FeedKillmail`, `FeedMonitoredSystem` (see `backend/campaigns/README.md`) |
| Feed page and warzone briefing | `GET /api/feed/`, `GET /api/feed/warzone` (`feed/router.py`) |
| Fleet results and history | `fleet_kills` events via `FeedEventFleetLink` |
| Desktop Intel window | `FeedCapitalAlert` and `FeedAmarrFleetAlert` (`intel/services/recent.py`); pilot affiliations from `FeedCharacterAffiliation` (`intel/services/local.py`) |
| Discord | Capital kill pings and Amarr fleet pings, to channels flagged `receive_capital_pings` and the Amarr fleet channel |
