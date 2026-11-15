# Fleet role training

The Fleet Roles guides teach the six jobs in our fleets, grouped as a pyramid: build the fleet (Damage), support it
(Remote Repair, Fleet Support) and disrupt the enemy (Capacitor Warfare, Electronic Warfare, Fleet Disruption). Each
guide has short lessons, the ships for the role, drills, checked outside resources, and ends with the pilots who fly
the role most.

## The roles

| Role | Guide | Ships | Ships come from |
| --- | --- | --- | --- |
| Damage | `/learning/guides/damage-guide/` | Typhoon, Typhoon Fleet Issue, Tempest Fleet Issue, Apocalypse Navy Issue | Doctrines (damage slots) |
| Remote Repair | `/learning/guides/remote-repair-guide/` | Zarmazd, Guardian, Augoror, Exequror | Doctrines (logistics slots) |
| Fleet Support | `/learning/guides/fleet-support-guide/` | Devoter, Huginn, Loki, Barghest, Vindicator | Listed in the guide |
| Capacitor Warfare | `/learning/guides/capacitor-warfare-guide/` | Armageddon, Ashimmu / Curse / Legion, Bhaalgorn (a ladder) | Listed in the guide |
| Electronic Warfare | `/learning/guides/electronic-warfare-guide/` | Griffin, Kitsune, Scorpion, Tengu | Listed in the guide |
| Fleet Disruption | `/learning/guides/fleet-disruption-guide/` | Stabber Fleet Issue, Bifrost, Heretic, Nestor | Listed in the guide |

Only Damage and Remote Repair are tied to doctrines: their ship cards show the doctrines that fly each hull and the
reader's readiness. The other guides are about specialty ships, so each card says what the ship is for
(`ship_jobs` in the guide data) instead.

The landing page is `/learning/guides/fleet-roles/`: learn, practice, fly, then the six roles as image tiles in the
pyramid. The Learning Center's first tab is **Fleet roles** and shows the same tiles (`RoleTile.astro`).

## The guide template

Every guide renders these sections in this order (`frontend/app/src/components/blocks/role-guide/RoleGuide.astro`):

1. **Why this role wins fights**, with an optional lead video.
2. **Ships for this role**: doctrine-backed cards (Damage, Remote Repair), job cards (Fleet Support, Electronic
   Warfare, Fleet Disruption) or the ladder (Capacitor Warfare). Readiness comes from `GET /api/training/hulls`,
   loaded by `role_ladder_component`.
3. **Lessons**: text, lists with ship or module icons, module panels, diagrams, EVE Academy clips and EVE Combat Sim
   scenarios to practice in the browser.
4. **Mistakes that lose fights.**
5. **Drills**, each with a Mark done button.
6. **Go deeper**: our own guides first, then checked outside videos, wiki pages, CCP material and tools, as media
   cards.
7. **Who flies this role**: the pilots who flew the role's ships on the most fleets in the last 90 days
   (`backend/capabilities/role_spotlight.py`, `GET /api/training/roles`, logged-in members only, cached for an hour),
   and a link to the reader's capabilities on the Training tab.

Guide content lives in `frontend/app/src/data/fleet-roles/`, one file per role. Prose quotes module numbers as `{key}`
tokens that `fill_facts` replaces from the SDE constants. The Damage guide's ammo charts come from
`src/data/fleet-roles/ammo.json`, written from the SDE by `frontend/app/scripts/extract_ammo_charts.mjs`.

Practice links go to EVE Combat Sim (eve-cs.com). The site has no simulators of its own.

## Learnings

Migration `backend/learning/migrations/0006_seed_fleet_role_learnings.py` seeds a Learning row for each guide and
drill, so drill completions are stored like any other learning. There are no fleet role certificates.

## Visibility

`FLEET_ROLES_LISTED` (in `src/data/fleet-roles/index.ts`) is true: the Training tab links each role to its guide. The
guides are indexed, but `hiddenFromIndex` keeps them out of the Guides catalog, since the Fleet roles tab links them.

The Learning Center's certificates are hidden, not removed: `SHOW_CERTIFICATES` in `LearningCenterHub.astro` brings
them back.

## Decisions

- **D1. Split Support** into Capacitor Warfare and Electronic Warfare in the capability engine.
- **D2. Positioning split** into Fleet Support and Fleet Disruption.
- **D3. Doctrines** drive the ships only for Damage and Remote Repair.
- **D4. No certificates** for these guides. Drills are marked done by hand.
- **D5. External simulators** are linked, never embedded.
- **D6. Logi FC** is a lesson in Remote Repair, not its own guide.
