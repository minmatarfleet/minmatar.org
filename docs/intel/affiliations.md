# Intel affiliation database

Who really flies for whom. Some groups aren't in a big alliance on paper but are that alliance in practice: alt alliances, pets and pilots who always fly with them. The affiliation database learns these from kill history, the intel team confirms them, and every intel tool groups pilots by the result.

The example it was tuned on is Scary Wormhole People (alliance 99010022, run by the corp TDSIN). It had Snuffed Out on 20% of its sampled kills, in all 12 of its active months, while it was only 1.9% of Snuffed Out's kills.

## Words

- **Bloc**: a real-world group, named by us (`IntelBloc`). It is anchored on its main alliance, which belongs to it without an affiliation row.
- **Affiliation**: a subject (alliance, corporation or character) belonging to a bloc (`IntelAffiliation`). It has a relation, a status and its evidence.
  - Relations: `pet`, `alt` (alt alliance), `ally`, `associate` (a pilot outside the bloc who keeps flying with it), `member`.
  - Statuses: `suggested` (shown as "likely"), `confirmed`, `rejected`.
  - `ended` means an inferred row has had no evidence for six months (a former pet).

## How it fills up

All code is in `backend/intel/affiliations/`. Thresholds and their reasons are in `constants.py`.

1. **Sightings** (`sightings.py`, hourly). These count every group seen since the last pass:
   - attackers and victims on feed killmails;
   - alliances, and corporations outside an alliance, in shared Local reports. A Local report counts three sightings, so it queues the group at once.

   A group is queued after three sightings. It is queued again when it is still seen 30 days after its last investigation, and 6 hours after a failed one.
2. **Investigation** (`investigate.py`, every 10 minutes, three groups a run, highest priority first).
   - For each of the last 24 months, it reads one zKill page of the group's kills and one of its losses. zKill returns full killmails, 200 a page, so no ESI call is made per mail.
   - Each month becomes `IntelCoAttack` rows:
     - `shared`: the group's sampled kills the partner was also on;
     - `militia_shared`: the shared kills where both flew for the same militia;
     - `against`: the group's sampled losses the partner shot.
   - Mails with more than 60 attackers are skipped (blobs and structure bashes). NPC corporations are never groups.
   - A month that had ended when it was read is never read again, so a re-investigation costs about two months.
3. **Scoring** (`score.py`). It runs after each investigation and nightly for everything.
   - A **pet** has the partner on at least 20% of its kills, in at least 3 months, and leans on it at least twice as much as the reverse. If kills between the two exceed 20% of the shared ones, the link is ruled out. Below that, they lower the confidence.
   - Each group is judged over the whole 24 months and over the last 12, and the stronger lean wins.
   - Two groups that lean on each other about equally are **allies**; the smaller one joins the bigger one's bloc.
   - Shared kills mostly flown for the same militia are skipped: Local already shows militia by faction.
   - A partner is only judged once its own history is in, so scoring queues it first.
   - After a main's investigation, its ten most frequent partners are queued. Pets are a small share of a main's kills, so this is how they are found.
   - An **associate** is a character outside the bloc on at least 6 of its sampled kills, across at least 3 months. Our own characters are never suggested; they are listed in the members check instead.
4. **Review** (website, `intel.affiliations` feature). The intel team can:
   - confirm (optionally correcting the relation or the bloc) or reject a suggestion;
   - add affiliations by hand (always confirmed);
   - rename blocs, add notes, and merge one bloc into another.

   Scoring never changes a confirmed row's relation or status and never touches a rejected one.

## Reading it

`intel.affiliations.resolve` is the one lookup. `bloc_for(character_id=, corporation_id=, alliance_id=)` checks the pilot's own affiliation first, then their corporation's, then their alliance's. `bloc_for_group(kind, id)` does the same for one group.

- The whole live table is one map, cached for ten minutes. It is dropped on every write, and a cache outage reads the database instead.
- A bloc made by scoring only resolves once it has a live affiliation. One the intel team made or named always does.
- Pass `confirmed_only=True` where a guess must not appear.

Readers:

| Where | What | Shows suggested? |
| --- | --- | --- |
| Local summary (`intel/services/local.py`): desktop Intel window and `/intel/scans/<id>` | `blocs` (pilots per bloc and per group in it), `bloc` on each alliance row, `corporations` (pilots outside an alliance, by corp) | yes, marked likely |
| Capital pings (`feed/helpers/capital_pings.py`) | `**Bloc:** <name> · N of M attackers` | no: pings are never edited |
| Battle reports (`GET /api/fleets/{id}/fights/{n}/report`) | `bloc` on each group, for viewers with `intel.view` | yes, marked likely |
| Members check (`GET /api/intel/affiliations/members`) | our pilots who keep turning up on another bloc's kills (militia kills excluded) | n/a |

## Sensitivity

The database is intel: it shows what we know about other groups. Access is split like this:
- Bloc names appear in the tools only for pilots who can see intel (`intel.view`).
- The evidence, the review queue and the members check need `intel.affiliations`.
- The members check produces leads, not proof: a merc contract or a third party on the same brawl looks the same.

## Operations

- The work runs on the `intel` queue (`celery-intel` worker). See [the queue table](../architecture/celery-queues.md).
- To investigate a group now and print its top partners: `manage.py intel_investigate alliance 99004901`. Add `--score` to also suggest its bloc. The website's "Investigate now" queues it ahead of everything else instead.
- `manage.py intel_investigate` and the tasks need zKill. If zKill is down, the group is marked failed and retried six hours later; the months already read are kept.
