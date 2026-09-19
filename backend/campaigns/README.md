# Campaigns

Live, multi-system Faction Warfare campaigns. A campaign is a named operation
over a handful of warzone systems that runs for a month or two; everything an
enlisted pilot does inside those systems is counted.

The product specification is `docs/campaigns/fw-campaigns-plan.md`. This file
records what the code actually does today.

## How a fact gets in

| Fact | Path | Notes |
| --- | --- | --- |
| Kills and losses | zKill stream → `feed.helpers.ingest` → `services.attribution` | The hook runs on every ingest path. `sweep_campaign_killmails` re-attributes the last 48 hours every 10 minutes. |
| Complexes, advantage sites, supply caches | ESI character notifications → `services.sites` | `FacWarLPPayout*` is the only per-pilot record that a site was run. Polled every 20 minutes per included character. |
| Complex class | `services.sites.infer_complex_class` | Recovered from the payout amount, the split, the operational state, the contested factor and the insurgency stage. |
| Contested percent, victory points | public ESI FW systems feed → `services.snapshots` | Stored durably per campaign system; the feed's own table keeps eight days and discards victory points. |
| Operational state | `services.jump_graph` | Needs the warzone jump-graph fixture. Without it every system reports `unknown` and complex inference drops to low confidence. |
| Advantage | `services.advantage` | Our contribution is exact from payouts. The absolute value is crowd-read from pilot reports, with consensus, staleness and outlier holds. |
| Timeline | `services.snapshots.mirror_feed_events` | The activity feed's own events, mirrored. Detections, never scoring input. |
| Points | `services.scoring` + `services.stats` | Recomputed from source into `CampaignParticipantDay`, never incremented. Every board reads those rows. |

## Deliberate limits

- **No backfill.** A campaign is created before it starts, and attribution
  only counts a character while it was included. `seed_campaign_dev` breaks
  this rule on purpose and is development only.
- **Unconfirmed event codes never score.** The calibration table ships with
  event 371 and 367 confirmed; 516 and 359 are stored, displayed and left
  unscored until somebody confirms what they are. See the plan's open
  questions.
- **Ambiguous complexes are not named.** Several base LP tiers are exact
  multiples of each other, so a solo 15,000 plex and a 30,000 plex shared
  with one untracked pilot pay the same. Those rows keep their candidate list
  and stay unnamed; only an unambiguous tier gets a class.
- **Estimated advantage never scores.** A reading older than three hours is
  shown as an estimate and is excluded from objectives.

## Not implemented yet

Wired to the contract but not doing the work: the ESI fleet invite for
`standing-fleet/join` (ticket 10), gang fleet creation through the quick-start
path (ticket 11), notifications (ticket 14) and the whole Phase 1b community
layer. `services.esi_gate` keeps its own ledger and reads ESI's headers where
it can see them, but the platform-wide limiter is still a separate job.

## Running it locally

```bash
python manage.py migrate
python manage.py seed_campaign_dev --reset      # dev data from the local feed
python manage.py test campaigns --settings=app.settings_test
```

`seed_campaign_dev` builds the campaign from real killmails already in the dev
database, then adds synthetic LP payouts shaped like the real notifications,
because the dev database has no character notifications of its own.
