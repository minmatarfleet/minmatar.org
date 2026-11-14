# Fleet role training

The Fleet Roles guides teach the five jobs that decide fights: Damage, Remote Repair, Capacitor Warfare, Electronic
Warfare and Positioning Warfare. Each guide has the same eight sections, a ship ladder with the reader's own readiness,
browser simulators with targets, drills that count toward a Learning Center certificate, and checked outside resources.

Status: complete. The guides need no new content from people; "Content without new recordings" at the end shows what
fills each slot the design held for alliance-made material.

## The roles

| Role | Guide | Ladder (entry to endgame) | Capability classes it counts |
| --- | --- | --- | --- |
| Damage | `/learning/guides/damage-guide/` | Typhoon, Typhoon Fleet Issue, Tempest Fleet Issue / Apocalypse Navy Issue | DPS |
| Remote Repair | `/learning/guides/remote-repair-guide/` | Augoror / Exequror, Guardian, Zarmazd | Logistics |
| Capacitor Warfare | `/learning/guides/capacitor-warfare-guide/` | Armageddon, Ashimmu / Curse / Legion, Bhaalgorn | Capacitor Warfare, Support |
| Electronic Warfare | `/learning/guides/electronic-warfare-guide/` | Griffin, Kitsune, Scorpion, Tengu | Electronic Warfare, Support |
| Positioning Warfare | `/learning/guides/positioning-warfare-guide/` | Stabber Fleet Issue, Bifrost, Heretic, Devoter | Tackle |

The hub is `/learning/guides/fleet-roles/`. The Capacitor Warfare and Electronic Warfare classes come from splitting the
engine's Support class (decision D1 below); until that ships, both guides read "Support".

Interdiction bubbles only work in null-sec, wormholes and low-sec at corruption level 5, so in most of the warzone the
Positioning guide teaches points, the heavy interdictor's focused script, Micro Jump Field Generators and bumping, and
bubbles for the fleets that leave it.

## The guide template

Every guide renders these sections in this order (`frontend/app/src/components/blocks/role-guide/RoleGuide.astro`):

1. **Why this role wins fights**, with an optional lead video and an "In our fleets" note on where the role shows up in our doctrines and battlefields.
2. **The ladder**: ship cards. Each card lists the current doctrines that fly the hull and the slot it fills (Primary, Academy, Support, Utility), read live from the public doctrines API, so the ladder never names a retired doctrine. A logged-in reader sees their best character's readiness on each hull and a link to the
   doctrine fit, from `GET /api/training/hulls` (`backend/capabilities/endpoints/get_hulls.py`), loaded by
   `role_ladder_component`.
3. **The mechanics**: the featured simulator, then each lesson (read, simulator, video or diagram).
4. **On grid**: what the FC says at each phase of a fight, and what you do.
5. **Mistakes that lose fights.**
6. **Drills**: a simulator drill completes itself when the simulator is beaten (the simulator dispatches
   `fleet-role-sim:beaten` and `role_drills_component` posts the completion); a fleet drill has a Mark done button.
7. **Go deeper**: our own guides and site tools first (New Player Fleet Guide, Faction Warfare Battlefields, Doctrines, d-scan, Skill plans, the Training tab), then outside videos, EVE University pages, CCP dev blogs and tools, each opened and checked.
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

Migration `backend/learning/migrations/0008_seed_fleet_roles_certificate.py` seeds the **Fleet Roles** certificate,
earned with any three of the five role certificates. A certificate can now be earned through other certificates
(`Certificate.required_certificates` and `required_count`); the certificate page lists them and counts the ones the
reader holds.

## Training tab

Each row of "Ready by role" on a character links to the role's guide.

## Decisions

- **D1. Split Support** into Capacitor Warfare and Electronic Warfare in the capability engine. Built on the feat/fleet-role-taxonomy branch with fleet role coverage for interdiction, ECM and neuts, kept separate so it can be reviewed on its own.
- **D2. The ladders** follow the brief, adjusted to how we fly (the Scorpion is the second Electronic Warfare rung). Each card shows the doctrines that fly the hull today, so the ladder stays honest as doctrines change.
- **D4. Drills**: simulators and fleets satisfy every drill; Singularity drills are optional and do not count.
- **D5. External simulators** are linked from Go deeper, never depended on.
- **D6. Logi FC** is a lesson in Remote Repair, not its own guide.

## Content without new recordings

Every slot the original design held for alliance-made content is filled from what already exists:

| Slot | Filled with |
| --- | --- |
| A video in each Why section and in the video lessons | Checked outside videos (The Brave Dojo, EVE University, Gildii Auscent, Fua Consternation, Shizuka's Station, Imperium News, Zip Slings, Pandemic Horde), each confirmed to exist |
| A fight from our history | "Recent fleets that flew it": the finished fleets of the last 60 days that brought the most pilots in the role's ladder ships, each linking to its fleet page and battle report (`backend/capabilities/role_spotlight.py`, `GET /api/training/roles`), under the "In our fleets" note |
| Named FCs and mentors | "Pilots who fly it most": the five pilots who flew the role's ladder ships on the most fleets this year, by name and portrait, plus the mentor finder for one-to-one classes |
| Which ships we fly | Live doctrine tags on each ladder card, from the public doctrines API |
| Screenshots | The fleet window screenshot from the New Player Fleet Guide |

Simulator scenario text (target names, readouts) lives with the guide content in
`frontend/app/src/components/blocks/role-sims/role_sim_data.ts`, the same way the capital guides keep their content in
data files; the shared simulator frame's labels are in the i18n file.

Both live lists use only fleets anyone in the alliance may see (no private or members-only group fleets), are shown to
logged-in members only, and are cached for an hour.
