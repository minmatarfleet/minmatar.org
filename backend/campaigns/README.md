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
| Fleets | `services.fleets` | Attendance and fleet-linked kills come from the fleet instance members the existing ESI poller already writes, so campaigns add no polling of their own. A fleet counts once someone sets `campaign` on it. |
| Timeline | `services.snapshots.mirror_feed_events` | The activity feed's own events, mirrored per campaign. Detections, never scoring input. |
| Points | `services.scoring` + `services.stats` | Recomputed from source into `CampaignParticipantDay`, never incremented. Every board reads those rows. |
| Awards | `services.awards` | Six weekly awards decided from the same day rows every Thursday, three campaign awards at close-out. |

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
  shown as an estimate and is excluded from objectives. Re-reporting the same
  system only scores once every two hours.
- **Pods never score**, on either side. The ship loss already cost the pilot.
- **Every read is gated on the campaign's visibility.** The roster names
  pilots and the coverage chart shows when the alliance is *not* online, so
  only a campaign explicitly marked `public` is readable without the
  `campaigns.view` feature.
- **Being in the alliance is not being in the campaign.** Reporting
  advantage, taking the standing fleet and forming a gang all require an
  active enlistment in that campaign, and are refused once it has ended.

## Known limits

- ESI reports when a pilot **joined** a fleet but never when they left, so
  standing-fleet minutes are bounded by the last time the poller confirmed
  the fleet existed rather than measured exactly.
- Complex class can only be called certain for base tiers that are not a
  multiple of another tier, because a solo capture and a shared larger one
  pay identically. Everything else keeps its candidate list and stays
  unnamed.
- Operational state needs the SDE jump-graph fixture. Without it, or for a
  system the fixture predates, the state is `unknown` and inference drops to
  low confidence rather than guessing.

## Not implemented yet

An FC attributes a fleet to a campaign from the fleet form, and everything
downstream of that works: attendance, fleet-linked kills, the fleet bonus and
the softer loss penalty. What is still only a contract is the campaign
creating a fleet *for* you: the ESI invite behind `standing-fleet/join`
(ticket 10) and gang fleets through the quick-start path (ticket 11). Until
then `form_gang` announces a gang on the timeline rather than creating a
tracked fleet, and the standing fleet records who holds it rather than
opening one in game.

Also outstanding: notifications (ticket 14) and the whole Phase 1b community
layer, whose columns (`supply_isk_delivered`, `project_isk_earned`) exist but
are written by nothing yet. `services.esi_gate` keeps its own ledger and
reads ESI's headers where it can see them, but the platform-wide limiter is
still a separate job.

## Calibration

Event codes ship unconfirmed and unconfirmed codes never score. When somebody
establishes what a code actually is:

```bash
python manage.py confirm_fw_event_code 516 \
    --site-kind rendezvous_point --by "BearThatCares deployed one, 20 Sep"
```

That confirms the code and rescores the completions already recorded with it.
The table is also in the Django admin, but prefer the command: editing
`confirmed` by hand leaves the existing sites unscored.

## Running it locally

```bash
python manage.py migrate
python manage.py seed_campaign_dev --reset      # dev data from the local feed
python manage.py test campaigns --settings=app.settings_test
```

`seed_campaign_dev` builds the campaign from real killmails already in the dev
database, then adds synthetic LP payouts shaped like the real notifications,
because the dev database has no character notifications of its own.
