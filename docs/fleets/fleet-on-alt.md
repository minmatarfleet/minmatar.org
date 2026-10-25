# Running a fleet on an alt

An FC usually forms the fleet on their main. Sometimes they form it on another of their characters. The site keeps showing the FC as the person (their main) and adds the character they're running the fleet on in game.

Wireframes: the "Fleet on an alt" design canvas (Oct 2026).

## Starting the fleet

| Rule | |
|---|---|
| Default | Start tracking (and Start fleet now) uses the FC's main. One click; nothing to pick. |
| Main isn't boss | Without a chosen character, the start tries the main, then the FC's other characters by name, and uses the first that is fleet boss in game (`find_fleet_boss` in `fleets/helpers/fleet_boss.py`). The fleet page then says "Tracking on {alt}, your fleet boss". |
| None is boss | "None of your characters is the fleet boss (checked …)", naming the characters checked. An FC with only a main gets the old "Not currently in a fleet" / "Must be the fleet commander" errors. |
| Change | A quiet Change link under Start tracking lists the FC's characters, main first, and tags the one that is boss in game (from `GET /api/fleets/current`). Picking one starts on it (`fc_character_id`), as before. |
| Boss passed | The instance's `boss_id` follows the in-game boss. Passed to another of the FC's characters, the site shows that one; passed to someone else's character, it shows the FC's main again. |

## How it reads

The FC is their main everywhere: portrait, name, FC credit and stats. The in-game character is the alt (`EveFleet.fleet_commander_alt`), null when the FC runs the fleet on their main.

| Surface | Shows |
|---|---|
| Fleet responses | `fleet_commander_alt_character_id` / `fleet_commander_alt_name` next to the main's fields (`make_fleet_response`, `GET /api/fleets/{id}`). |
| Fleet page and lists | The main's portrait with the alt as a small inset in the bottom-right corner (the fleet-type flag keeps the top-left). Fleet page: "In game Henri Gray · Copy name". Rows: "BearThatCares as Henri Gray". |
| Start ping | Author is the main; an extra `FC IN GAME: {ALT}` line. No line on the main. |
| MOTD | The in-game character, never the main. |
| Desktop fleet window | `fc_alt_character_id` / `fc_alt_name` in the shared payload; the window shows "as {alt}". The FC's system is the alt's. |
| Public pages | Only the in-game character: the public kills report (`GET /api/fleets/{id}/public-kills`) and campaign fleet lists. Outsiders never see which main is behind an alt. |
