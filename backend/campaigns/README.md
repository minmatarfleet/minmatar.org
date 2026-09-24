# Campaigns

Live campaigns over a set of theaters: Faction Warfare systems, structure
recon, or both. A campaign is a named operation that runs for a month or two;
everything an enlisted pilot does inside those theaters is counted.

The product specification is `docs/campaigns/fw-campaigns-plan.md`. This file
records what the code actually does today.

## Campaign kinds

| Kind | Page reads as | Typical theaters |
| --- | --- | --- |
| `faction_warfare` | Contest, plexes, advantage, system cards | Listed FW systems; optional structures (e.g. Dal) |
| `strategic` | Opponent header, structure recon + timers, capital/ship boards | Structures and the systems they pull in |

Kinds are display presets. Matching is the same: an enlisted included character
on a mail in a listed system, or on a mail that destroys a campaign structure.

## Admin

Operators configure campaigns in Django admin (`/admin/campaigns/campaign/`).
The campaign list and detail pages show a cog for staff (or anyone with
`campaigns.change_campaign`) that opens the change form. From one campaign
change page you can edit identity (name, tagline, description), lifecycle,
commander's order, Discord, scoring JSON, systems (including `is_fw_objective`),
areas, opponents, structures, fittings and the standing fleet. Saving an FW
objective system with a goal auto-creates a default arc when none exists.

List actions on the campaign changelist:

- **Propose week targets from arcs** — runs `propose_week` for the selection
- **Draft commander's order from week plan** — fills the order text as draft
- **Publish commander's order** — clears the draft flag so members see it live

Week targets, arcs, enlistments and activity rows also have their own
changelists for deeper tweaks. Tagline, opponents, commander's order and
campaign fittings appear on the member-facing campaign pages; leave the
order as draft until you publish it. Linking a structure timer to a campaign
in admin (or via the timer API) creates the recon row and grows the theater.

## How a fact gets in

| Fact | Path | Notes |
| --- | --- | --- |
| Kills and losses | zKill stream → `feed.helpers.ingest` → `services.attribution` | The hook runs on every ingest path. `sweep_campaign_killmails` re-attributes the last 48 hours every 10 minutes. Systems added via structure attach get `FeedMonitoredSystem` with `source=campaign`. |
| Structure recon / timers | `services.structures.attach_*` · `EveStructureTimer.campaign` | Attaching a structure adds its system to the theater. Timer create (API) and saving a timer with a campaign in Django admin both call `attach_timer`. |
| Structure find-and-report week target | `plan.propose_week` · metric `structures_reported` | Strategic campaigns on ops systems (`is_fw_objective=False`) only; progress = structures created in that system this campaign week. |
| Ops areas (constellation / region) | `CampaignArea` | Guidance only; never FW objectives; never pull kill attribution. |
| Structure / capital flags | `services.attribution` + `STRUCTURE_TYPE_IDS` / `is_capital_ship_type` | Structure mails often have no victim character; enlisted attackers still count. |
| Complexes, advantage sites, supply caches | ESI character notifications → `services.sites` | FW only. Polled every 20 minutes per included character. |
| Contested percent, victory points | public ESI FW systems feed → `services.snapshots` | FW systems; strategic campaigns skip when they have no systems. |
| Advantage | `services.advantage` | Exact from payouts; crowd-read absolute value. |
| Fleets | `services.fleets` | A fleet counts once someone sets `campaign` on it. |
| Points | `services.scoring` + `services.stats` | Recomputed into `CampaignParticipantDay`. Boards include `structure_kills` / `capital_kills`. |
| Awards | `services.awards` | Six weekly + three campaign awards from day rows. |

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
- **Entity matching is theater-scoped.** Opponents label boards; they do not
  alone pull every CVA mail in New Eden into the campaign.

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
- Timer `alliance_name` / `system_name` are strings; attach resolves system
  id from the SDE / monitored list and alliance id from `EveAlliance` when
  known. Enemy citadels usually have no `EveStructure` FK.

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
