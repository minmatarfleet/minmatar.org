# Fleet role training

The Fleet Roles guides teach the five jobs that decide fights: Damage, Remote Repair, Capacitor Warfare, Electronic
Warfare and Positioning Warfare. Each guide has the same eight sections, a ship ladder with the reader's own readiness,
browser simulators with targets, drills that count toward a Learning Center certificate, and checked outside resources.

Status: the guides, simulators, certificates and Training tab links are built. Videos recorded by our own FCs, fight
stories from our fleet history, and named mentors per role are not: they need people (see "Not built yet").

## The roles

| Role | Guide | Ladder (entry to endgame) | Capability classes it counts |
| --- | --- | --- | --- |
| Damage | `/learning/guides/damage-guide/` | Typhoon, Typhoon Fleet Issue, Tempest Fleet Issue / Apocalypse Navy Issue | DPS |
| Remote Repair | `/learning/guides/remote-repair-guide/` | Augoror / Exequror, Guardian, Zarmazd | Logistics |
| Capacitor Warfare | `/learning/guides/capacitor-warfare-guide/` | Armageddon, Ashimmu / Curse / Legion, Bhaalgorn | Capacitor Warfare, Support |
| Electronic Warfare | `/learning/guides/electronic-warfare-guide/` | Griffin, Kitsune, Scorpion, Tengu | Electronic Warfare, Support |
| Positioning Warfare | `/learning/guides/positioning-warfare-guide/` | Stabber, Bifrost, Sabre, Broadsword | Tackle |

The hub is `/learning/guides/fleet-roles/`. The Capacitor Warfare and Electronic Warfare classes come from splitting the
engine's Support class (decision D1 below); until that ships, both guides read "Support".

Interdiction bubbles only work in null-sec, wormholes and low-sec at corruption level 5, so in most of the warzone the
Positioning guide teaches points, the heavy interdictor's focused script, Micro Jump Field Generators and bumping, and
bubbles for the fleets that leave it.

## The guide template

Every guide renders these sections in this order (`frontend/app/src/components/blocks/role-guide/RoleGuide.astro`):

1. **Why this role wins fights**, with an optional lead video.
2. **The ladder**: ship cards. A logged-in reader sees their best character's readiness on each hull and a link to the
   doctrine fit, from `GET /api/training/hulls` (`backend/capabilities/endpoints/get_hulls.py`), loaded by
   `role_ladder_component`.
3. **The mechanics**: the featured simulator, then each lesson (read, simulator, video or diagram).
4. **On grid**: what the FC says at each phase of a fight, and what you do.
5. **Mistakes that lose fights.**
6. **Drills**: a simulator drill completes itself when the simulator is beaten (the simulator dispatches
   `fleet-role-sim:beaten` and `role_drills_component` posts the completion); a fleet drill has a Mark done button.
7. **Go deeper**: outside videos, EVE University pages, CCP dev blogs and tools, each opened and checked.
8. **Ask, then certify**: the role's certificate and the mentor finder.

Guide content lives in `frontend/app/src/data/fleet-roles/`, one file per role. Prose quotes module numbers as
`{key}` tokens that `fill_facts` replaces from the SDE constants, so a balance change reaches the text on the next
extraction.

## Simulators

Eight simulators in `frontend/app/src/components/blocks/role-sims/`, built on pure engines in
`frontend/app/src/helpers/sims/` with unit tests in `frontend/app/testing/sims/`:

| Simulator | Guide | Engine |
| --- | --- | --- |
| Drag and stop bubbles | Positioning | `bubbles.ts` |
| Micro Jump Field Generator | Positioning | `mjfg.ts` |
| The capacitor curve | Capacitor | `capacitor.ts` |
| Neut pressure | Capacitor | `capacitor.ts` |
| Jam chance | Electronic Warfare | `ecm.ts` |
| ECM spread | Electronic Warfare | `ecm.ts` |
| The rep race | Remote Repair | `rep_race.ts` |
| Applied damage | Damage | `application.ts` |

Module and hull numbers come from `frontend/app/src/data/fleet-roles/sim_constants.json`, written from the SDE by
`frontend/app/scripts/extract_role_sim_constants.mjs`; a test re-derives it when the SDE file is present. Scenario
numbers that are not module attributes (incoming DPS on the rep race anchor, the fleet layout in the boosh simulator)
are chosen in `frontend/app/src/helpers/sims/scenarios.ts`, and the tests prove every target is reachable and none is
met at the start. Hull bonuses assume level V skills.

External simulators are linked, not embedded: EVE Combat Sim (eve-cs.com) and Pyfa's graphs.

## Certificates

Migration `backend/learning/migrations/0006_seed_fleet_role_certificates.py` seeds one certificate per role
(`fleet-role-<role>`): the guide, then each non-optional drill as a learning. The drills in the migration and in the
frontend data are kept in step by `backend/learning/tests/test_fleet_role_certificates.py`.

## Training tab

Each row of "Ready by role" on a character links to the role's guide.

## Decisions

- **D1. Split Support** into Capacitor Warfare and Electronic Warfare in the capability engine. Built in a separate pull
  request with fleet role coverage for interdiction, ECM and neuts, so it can be reviewed on its own.
- **D2. The ladders** above follow the brief. Role FCs should confirm them and add an Academy fit where a rung has none.
- **D4. Drills**: simulators and fleets satisfy every drill; Singularity drills are optional and do not count.
- **D5. External simulators** are linked from Go deeper, never depended on.
- **D6. Logi FC** is a lesson in Remote Repair, not its own guide.

## Not built yet

- Videos recorded by our own FCs, and a fight from our fleet history with its battle report in each "Why" section.
  The guides use checked outside videos meanwhile.
- A named FC author and mentors per role (D3). The guides link the mentor finder.
- A Fleet Roles certificate for any three roles: the award rule only knows "every learning in the certificate".
- Showing the Training tab level (Unlocked, Ready, Proven) next to each certificate.
- Simulator text in the i18n file; it is English in the simulator data today.
