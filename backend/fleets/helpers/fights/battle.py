"""Every killmail around a fleet's rounds, and its battle report.

The timeline's own rows only hold mails our fleet was on. A battle report
needs everything that died nearby: third parties, and allies who were not
in the fleet. Each rebuild snapshots every feed killmail in the matched
mails' systems from the first matched mail minus ``WINDOW_PAD`` to the last
plus ``WINDOW_PAD``, because the feed purges mails after 30 days. Taking the
whole span, not each round, keeps the snapshot right when an FC merges or
splits rounds later.

A snapshot row:

    {"id", "t" (ISO time), "system", "ship", "isk", "pod",
     "n" (attackers, NPCs included),
     "victim": {"character", "corporation", "alliance"},
     "attackers": [[character, corporation, alliance, ship, damage,
                    final_blow], ...] (NPCs left out),
     "partial" (only on rows rebuilt from the timeline's own row because
                the feed no longer had the mail)}

A report covers the whole fleet, or any window of it an FC saved as a
segment or a pilot picked on the activity strip. It filters the snapshot
to the window, then splits everyone into sides (``assign_sides``, pure) the
way br.evetools does, from the window's own mails.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta
from typing import Iterable

from django.db.models.fields.json import KeyTransform

from eveonline.killmail_classes import CAPSULE_TYPE_IDS
from feed.helpers.eve_names import resolve_type_names
from feed.helpers.fleet_kills import OUTCOME_LOSS, killmail_isk
from feed.models import FeedKillmail
from fleets.helpers.fights.collect import _named, lookup_entity_names
from fleets.helpers.fights.rounds import parse_time
from fleets.helpers.fights.rounds import FIRST_ALLIANCE_ID

WINDOW_PAD = timedelta(minutes=1)
MAX_TEAMS = 3
OUR_TEAM = 0

# Positions in a snapshot attacker list.
CHARACTER, CORPORATION, ALLIANCE, SHIP, DAMAGE, FINAL_BLOW = range(6)


# --------------------------------------------------------------- snapshot


def our_characters(rows: Iterable[dict]) -> set[int]:
    """Our fleet's pilots on the timeline's rows: attackers and losses."""
    ours: set[int] = set()
    for row in rows:
        ours.update(row.get("pilots") or ())
        if row.get("outcome") == OUTCOME_LOSS and row.get("victim"):
            ours.add(row["victim"])
    return ours


def _compact(killmail) -> dict:
    victim = killmail.raw_victim or {}
    summary = killmail.attacker_summary or []
    return {
        "id": killmail.killmail_id,
        "t": killmail.killmail_time.isoformat(),
        "system": killmail.solar_system_id,
        "ship": killmail.victim_ship_type_id,
        "isk": killmail_isk(killmail),
        "pod": killmail.victim_ship_type_id in CAPSULE_TYPE_IDS,
        "n": len(summary),
        "victim": {
            "character": killmail.victim_character_id,
            "corporation": victim.get("corporation_id"),
            "alliance": victim.get("alliance_id"),
        },
        "attackers": [
            [
                attacker.get("character_id"),
                attacker.get("corporation_id"),
                attacker.get("alliance_id"),
                attacker.get("ship_type_id"),
                attacker.get("damage_done") or 0,
                bool(attacker.get("final_blow")),
            ]
            for attacker in summary
            if attacker.get("character_id")
        ],
    }


def _split_group(group: int | None) -> tuple[int | None, int | None]:
    """``(corporation, alliance)`` for a bare group id."""
    if not group:
        return None, None
    if group >= FIRST_ALLIANCE_ID:
        return None, group
    return group, None


def partial_row(row: dict) -> dict:
    """A snapshot row from the timeline's own row, for a purged mail.

    Only the victim's group and who shot our losses survive there, so the
    report marks itself incomplete when it uses one.
    """
    corporation, alliance = _split_group(row.get("victim_group"))
    attackers = [
        [character, None, None, None, 0, False]
        for character in row.get("pilots") or ()
    ]
    for group, character in row.get("hostiles") or ():
        group_corporation, group_alliance = _split_group(group)
        attackers.append(
            [character, group_corporation, group_alliance, None, 0, False]
        )
    return {
        "id": row["id"],
        "t": row["t"],
        "system": row["system"],
        "ship": row.get("ship"),
        "isk": row.get("isk") or 0,
        "pod": bool(row.get("pod")),
        "n": len(attackers),
        "victim": {
            "character": row.get("victim"),
            "corporation": corporation,
            "alliance": alliance,
        },
        "attackers": attackers,
        "partial": True,
    }


def collect_battle(rows: list[dict]) -> list[dict]:
    """Every feed killmail around the matched ``rows``, oldest first.

    One query on the (system, time) index; the raw mail's victim is read
    with a JSON key lookup so the heavy item list never loads. Matched
    mails the feed has purged come back as partial rows.
    """
    if not rows:
        return []
    systems = sorted({row["system"] for row in rows})
    times = [parse_time(row["t"]) for row in rows]
    killmails = (
        FeedKillmail.objects.filter(
            solar_system_id__in=systems,
            killmail_time__gte=min(times) - WINDOW_PAD,
            killmail_time__lte=max(times) + WINDOW_PAD,
        )
        .only(
            "killmail_id",
            "killmail_time",
            "solar_system_id",
            "victim_character_id",
            "victim_ship_type_id",
            "attacker_summary",
            "zkb_meta",
        )
        .annotate(raw_victim=KeyTransform("victim", "raw_killmail"))
        .order_by("killmail_time", "killmail_id")
    )
    battle = [_compact(killmail) for killmail in killmails]
    found = {row["id"] for row in battle}
    battle += [partial_row(row) for row in rows if row["id"] not in found]
    return sorted(battle, key=lambda r: (r["t"], r["id"]))


def resolve_battle_names(
    battle: list[dict], prior: dict | None, timeline_names: dict | None
) -> dict:
    """Pilot, corporation, alliance and ship names on the snapshot.

    Names already stored (on the snapshot or the timeline) are reused, so a
    live rebuild only asks ESI about pilots it has not seen.
    """
    prior = prior or {}
    timeline_names = timeline_names or {}
    characters: set[int] = set()
    groups: set[int] = set()
    ships: set[int] = set()
    for row in battle:
        victim = row["victim"]
        characters.add(victim["character"])
        groups.update((victim["corporation"], victim["alliance"]))
        ships.add(row["ship"])
        for attacker in row["attackers"]:
            characters.add(attacker[CHARACTER])
            groups.update((attacker[CORPORATION], attacker[ALLIANCE]))
            ships.add(attacker[SHIP])
    characters.discard(None)
    groups.discard(None)
    ships.discard(None)

    known_characters = {
        **(timeline_names.get("characters") or {}),
        **(prior.get("characters") or {}),
    }
    known_groups = {
        **(timeline_names.get("groups") or {}),
        **(prior.get("groups") or {}),
    }
    unknown = {c for c in characters if str(c) not in known_characters}
    unknown |= {g for g in groups if str(g) not in known_groups}
    resolved = lookup_entity_names(unknown)
    known_ships = prior.get("ships") or {}
    ship_names = resolve_type_names(
        s for s in ships if str(s) not in known_ships
    )
    return {
        "characters": _named(
            {c: resolved[c] for c in characters if c in resolved},
            {
                k: v
                for k, v in known_characters.items()
                if int(k) in characters
            },
        ),
        "groups": _named(
            {g: resolved[g] for g in groups if g in resolved},
            {k: v for k, v in known_groups.items() if int(k) in groups},
        ),
        "ships": {
            **known_ships,
            **{str(k): v for k, v in ship_names.items()},
        },
    }


def snapshot(timeline, *, now) -> None:
    """Take the battle snapshot for ``timeline``; the caller saves it."""
    battle = collect_battle(timeline.killmails or [])
    timeline.battle_killmails = battle
    timeline.battle_names = resolve_battle_names(
        battle, timeline.battle_names, timeline.names
    )
    timeline.battle_collected_at = now


def ensure_snapshot(timeline, *, now) -> None:
    """Backfill a timeline built before the snapshot existed.

    Runs once: when the feed has purged the mails, the snapshot is the
    timeline's own rows marked partial, and that is stored too.
    """
    if timeline.battle_collected_at is not None:
        return
    snapshot(timeline, now=now)
    timeline.save(
        update_fields=[
            "battle_killmails",
            "battle_names",
            "battle_collected_at",
        ]
    )


# ------------------------------------------------------------------ sides


def group_of(corporation: int | None, alliance: int | None) -> int | None:
    """The side-taking unit: the alliance, else the corporation."""
    return alliance or corporation or None


def alliance_ids(rows: Iterable[dict]) -> set[int]:
    """Every id that appears as an alliance on these mails."""
    found = set()
    for row in rows:
        if row["victim"]["alliance"]:
            found.add(row["victim"]["alliance"])
        found.update(a[ALLIANCE] for a in row["attackers"] if a[ALLIANCE])
    return found


def group_kind(group: int, alliances: set[int] | None = None) -> str:
    """Alliance or corporation, from the mails when we have them.

    Ids alone can't tell: alliances made before 2010 share the id range
    with corporations and characters, so the threshold is only a fallback.
    """
    if alliances is not None:
        return "alliance" if group in alliances else "corporation"
    return "alliance" if group >= FIRST_ALLIANCE_ID else "corporation"


def _victim_group(row: dict) -> int | None:
    victim = row["victim"]
    return group_of(victim["corporation"], victim["alliance"])


def _attacker_group(attacker: list) -> int | None:
    return group_of(attacker[CORPORATION], attacker[ALLIANCE])


def _pair(one: int, two: int) -> tuple[int, int]:
    return (one, two) if one < two else (two, one)


def side_weights(rows: list[dict]) -> tuple[Counter, Counter, Counter]:
    """``(hostile, friendly, involvement)`` between groups.

    hostile[(a, b)] counts mails where one shot the other; friendly[(a, b)]
    counts mails both shot together. Pairs are ordered (low id first).
    involvement counts the mails each group is on.
    """
    hostile: Counter = Counter()
    friendly: Counter = Counter()
    involvement: Counter = Counter()
    for row in rows:
        victim = _victim_group(row)
        shooters = {_attacker_group(a) for a in row["attackers"]}
        shooters.discard(None)
        for group in shooters | {victim}:
            if group is not None:
                involvement[group] += 1
        if victim is not None:
            for group in shooters:
                if group != victim:
                    hostile[_pair(group, victim)] += 1
        ordered = sorted(shooters)
        for index, one in enumerate(ordered):
            for two in ordered[index + 1 :]:
                friendly[(one, two)] += 1
    return hostile, friendly, involvement


def parse_sides(text: str | None, groups: Iterable[int]) -> dict[int, int]:
    """``"99000001:1,98000002:0"`` as {group: team}; bad entries dropped."""
    present = set(groups)
    moves: dict[int, int] = {}
    for part in (text or "").split(","):
        group, separator, team = part.strip().partition(":")
        if not separator:
            continue
        try:
            group_id, index = int(group), int(team)
        except ValueError:
            continue
        if group_id in present and 0 <= index < MAX_TEAMS:
            moves[group_id] = index
    return moves


def format_sides(moves: dict[int, int]) -> str:
    return ",".join(f"{group}:{team}" for group, team in sorted(moves.items()))


def _neighbours(
    hostile: Counter, friendly: Counter
) -> dict[int, dict[int, list[int]]]:
    """{group: {other: [friendly, hostile]}} for every pair that met."""
    neighbours: dict[int, dict[int, list[int]]] = defaultdict(dict)
    for slot, weights in ((0, friendly), (1, hostile)):
        for (one, two), count in weights.items():
            for group, other in ((one, two), (two, one)):
                neighbours[group].setdefault(other, [0, 0])[slot] += count
    return neighbours


def _choose_team(met: dict[int, list[int]], teams: dict[int, int]) -> int:
    """Where an unplaced group goes, given the groups placed so far.

    ``met`` is the group's row of ``_neighbours``. The team it fought
    alongside the most (net of fighting it), else a team it never fought
    (preferring not ours), else a new team, else the one it fought least.
    A group that never met any placed group is a third party: a new team,
    else the last one.
    """
    used = sorted(set(teams.values()))
    free = [team for team in range(1, MAX_TEAMS) if team not in used]
    towards: dict[int, list[int]] = {team: [0, 0] for team in used}
    for other, (friends, fights) in met.items():
        if other in teams:
            towards[teams[other]][0] += friends
            towards[teams[other]][1] += fights
    if not any(f or h for f, h in towards.values()):
        return free[0] if free else used[-1]
    allies = [team for team in used if towards[team][0] > 0]
    if allies:
        return max(
            allies,
            key=lambda t: (towards[t][0] - towards[t][1], towards[t][0], -t),
        )
    peaceful = [team for team in used if towards[team][1] == 0]
    if peaceful:
        return min(peaceful, key=lambda t: (t == OUR_TEAM, t))
    if free:
        return free[0]
    return min(used, key=lambda t: (towards[t][1], t))


def assign_sides(
    rows: list[dict], ours: set[int], sides: str | None = None
) -> tuple[dict[int, int], str]:
    """Put every group on the rows on team 0, 1 or 2. Pure.

    Team 0 is the groups our pilots fly in. Team 1 starts with the group
    that fought team 0 the most. Then, the group with the most contact with
    the placed groups first, each group joins the team it fought alongside,
    or a team it never fought; a group that fought every team and helped
    none starts team 2 (a third party). ``sides`` overrides the result
    group by group. Returns ``({group: team}, normalised sides)``.
    """
    hostile, friendly, involvement = side_weights(rows)
    neighbours = _neighbours(hostile, friendly)
    teams: dict[int, int] = {}
    for row in rows:
        victim = row["victim"]
        if victim["character"] in ours:
            group = _victim_group(row)
            if group is not None:
                teams[group] = OUR_TEAM
        for attacker in row["attackers"]:
            group = _attacker_group(attacker)
            if attacker[CHARACTER] in ours and group is not None:
                teams[group] = OUR_TEAM

    remaining = {g for g in involvement if g not in teams}
    # Contact with the placed groups, kept up to date as groups are placed.
    contact: Counter = Counter()
    for group in teams:
        for other, (friends, fights) in neighbours[group].items():
            contact[other] += friends + fights
    if remaining:
        pressure = {
            g: sum(
                fights
                for other, (_, fights) in neighbours[g].items()
                if teams.get(other) == OUR_TEAM
            )
            for g in remaining
        }
        seed = max(remaining, key=lambda g: (pressure[g], involvement[g], -g))
        if pressure[seed] > 0:
            teams[seed] = 1
            remaining.discard(seed)
            for other, (friends, fights) in neighbours[seed].items():
                contact[other] += friends + fights

    while remaining:
        group = max(remaining, key=lambda g: (contact[g], involvement[g], -g))
        teams[group] = _choose_team(neighbours[group], teams) if teams else 1
        remaining.discard(group)
        for other, (friends, fights) in neighbours[group].items():
            contact[other] += friends + fights

    moves = parse_sides(sides, involvement)
    teams.update(moves)
    return teams, format_sides(moves)


# ----------------------------------------------------------------- report


def _name(names: dict, kind: str, key, fallback: str) -> str:
    if key is None:
        return fallback
    return (names.get(kind) or {}).get(str(key)) or fallback


def _report_names(timeline) -> dict:
    stored = timeline.names or {}
    battle = timeline.battle_names or {}
    return {
        kind: {**(stored.get(kind) or {}), **(battle.get(kind) or {})}
        for kind in ("systems", "ships", "groups", "characters")
    }


class _Pilot:
    def __init__(self, character: int):
        self.character = character
        self.corporation = None
        self.alliance = None
        self.ships: list[dict] = []
        self.kills = 0
        self.damage = 0

    def seen(self, corporation, alliance):
        if corporation or alliance:
            self.corporation, self.alliance = corporation, alliance

    def flew(self, ship):
        if ship and all(entry["type_id"] != ship for entry in self.ships):
            self.ships.append({"type_id": ship, "lost": False, "id": None})

    def lost(self, ship, killmail_id):
        for entry in self.ships:
            if entry["type_id"] == ship and not entry["lost"]:
                entry.update(lost=True, id=killmail_id)
                return
        self.ships.append({"type_id": ship, "lost": True, "id": killmail_id})


def _pilots(rows: list[dict]) -> dict[int, _Pilot]:
    pilots: dict[int, _Pilot] = {}
    for row in rows:
        for attacker in row["attackers"]:
            pilot = pilots.setdefault(
                attacker[CHARACTER], _Pilot(attacker[CHARACTER])
            )
            pilot.seen(attacker[CORPORATION], attacker[ALLIANCE])
            pilot.flew(attacker[SHIP])
            pilot.kills += 1
            pilot.damage += attacker[DAMAGE] or 0
        victim = row["victim"]
        if victim["character"]:
            pilot = pilots.setdefault(
                victim["character"], _Pilot(victim["character"])
            )
            pilot.seen(victim["corporation"], victim["alliance"])
            pilot.lost(row["ship"], row["id"])
    return pilots


def _team_of(teams: dict[int, int], group, character, ours: set[int]):
    if group is not None and group in teams:
        return teams[group]
    # No known group (only on partial rows): ours, or the other side.
    return OUR_TEAM if character in ours else 1


def _team_totals(team: int, rows: list[dict], row_teams, shooters) -> dict:
    lost = [r for r in rows if row_teams[r["id"]] == team]
    killed = [
        r
        for r in rows
        if row_teams[r["id"]] != team and team in shooters[r["id"]]
    ]
    isk_lost = sum(r["isk"] for r in lost)
    isk_destroyed = sum(r["isk"] for r in killed)
    return {
        "ships_lost": sum(1 for r in lost if not r["pod"]),
        "pods_lost": sum(1 for r in lost if r["pod"]),
        "isk_lost": isk_lost,
        "isk_destroyed": isk_destroyed,
        "efficiency": (
            round(100 * isk_destroyed / (isk_destroyed + isk_lost))
            if isk_destroyed + isk_lost
            else None
        ),
    }


def _killmail(row: dict, names: dict, team: int) -> dict:
    victim = row["victim"]
    final = next((a for a in row["attackers"] if a[FINAL_BLOW]), None)
    return {
        "id": row["id"],
        "time": row["t"],
        "system_id": row["system"],
        "system_name": _name(
            names, "systems", row["system"], f"System {row['system']}"
        ),
        "ship_type_id": row["ship"],
        "ship_name": _name(names, "ships", row["ship"], "Unknown ship"),
        "victim_id": victim["character"],
        "victim_name": _name(names, "characters", victim["character"], ""),
        "victim_corporation_id": victim["corporation"],
        "victim_alliance_id": victim["alliance"],
        "victim_group_id": _victim_group(row),
        "team": team,
        "isk": row["isk"],
        "pod": bool(row["pod"]),
        "attackers": row.get("n", len(row["attackers"])),
        "final_blow": (
            {
                "character_id": final[CHARACTER],
                "name": _name(names, "characters", final[CHARACTER], ""),
                "ship_type_id": final[SHIP],
            }
            if final
            else None
        ),
    }


def _team_pilots(pilots: list[_Pilot], names: dict) -> list[dict]:
    result = [
        {
            "character_id": pilot.character,
            "name": _name(names, "characters", pilot.character, ""),
            "corporation_id": pilot.corporation,
            "corporation_name": _name(names, "groups", pilot.corporation, ""),
            "alliance_id": pilot.alliance,
            "alliance_name": _name(names, "groups", pilot.alliance, ""),
            "group_id": group_of(pilot.corporation, pilot.alliance),
            "ships": [
                {
                    "type_id": entry["type_id"],
                    "name": _name(
                        names, "ships", entry["type_id"], "Unknown ship"
                    ),
                    "lost": entry["lost"],
                    "killmail_id": entry["id"],
                }
                for entry in pilot.ships
            ],
            "kills": pilot.kills,
            "damage": pilot.damage,
        }
        for pilot in pilots
    ]
    return sorted(
        result,
        key=lambda p: (
            -p["damage"],
            -p["kills"],
            p["name"],
            p["character_id"],
        ),
    )


def _team_groups(
    groups: list[int],
    pilots: list[_Pilot],
    lost: list[dict],
    names: dict,
    alliances: set[int],
) -> list[dict]:
    pilot_counts = Counter(
        group_of(pilot.corporation, pilot.alliance) for pilot in pilots
    )
    ships_lost: Counter = Counter()
    isk_lost: Counter = Counter()
    for row in lost:
        group = _victim_group(row)
        isk_lost[group] += row["isk"]
        if not row["pod"]:
            ships_lost[group] += 1
    result = [
        {
            "id": group,
            "kind": group_kind(group, alliances),
            "name": _name(
                names,
                "groups",
                group,
                f"Unknown {group_kind(group, alliances)}",
            ),
            "pilots": pilot_counts.get(group, 0),
            "ships_lost": ships_lost.get(group, 0),
            "isk_lost": isk_lost.get(group, 0),
        }
        for group in groups
    ]
    return sorted(
        result, key=lambda g: (-g["pilots"], -g["isk_lost"], g["name"])
    )


def _battle(timeline) -> tuple[list[dict], bool]:
    """The snapshot rows, and whether the feed had them all."""
    collected = timeline.battle_collected_at is not None
    battle = (
        timeline.battle_killmails
        if collected
        else [partial_row(row) for row in timeline.killmails or []]
    )
    return battle, collected


def _report(timeline, rows: list[dict], sides: str | None) -> dict:
    """Teams, sides and killmails for ``rows``.

    ``isk_destroyed`` for a team is the ISK every other team lost on mails
    where that team had at least one attacker, so a mail shot by two teams
    counts for both.
    """
    names = _report_names(timeline)
    ours = our_characters(timeline.killmails or [])
    teams, normalised = assign_sides(rows, ours, sides)
    alliances = alliance_ids(rows)

    pilots = _pilots(rows)
    pilot_teams = {
        character: _team_of(
            teams, group_of(pilot.corporation, pilot.alliance), character, ours
        )
        for character, pilot in pilots.items()
    }
    row_teams = {
        row["id"]: _team_of(
            teams, _victim_group(row), row["victim"]["character"], ours
        )
        for row in rows
    }
    shooters = {
        row["id"]: {
            _team_of(teams, _attacker_group(a), a[CHARACTER], ours)
            for a in row["attackers"]
        }
        for row in rows
    }
    indexes = sorted(
        {OUR_TEAM, 1} | set(teams.values()) | set(pilot_teams.values())
    )
    by_team: dict[int, list[_Pilot]] = defaultdict(list)
    for character, pilot in pilots.items():
        by_team[pilot_teams[character]].append(pilot)
    report_teams = []
    for index in indexes:
        lost = [r for r in rows if row_teams[r["id"]] == index]
        report_teams.append(
            {
                "index": index,
                "ours": index == OUR_TEAM,
                "totals": {
                    "pilots": len(by_team[index]),
                    "damage": sum(p.damage for p in by_team[index]),
                    **_team_totals(index, rows, row_teams, shooters),
                },
                "groups": _team_groups(
                    sorted(g for g, t in teams.items() if t == index),
                    by_team[index],
                    lost,
                    names,
                    alliances,
                ),
                "pilots": _team_pilots(by_team[index], names),
            }
        )
    system_ids = sorted({row["system"] for row in rows})
    return {
        "systems": [
            {
                "id": system_id,
                "name": _name(
                    names, "systems", system_id, f"System {system_id}"
                ),
            }
            for system_id in system_ids
        ],
        "sides": normalised,
        "teams": report_teams,
        "killmails": [
            _killmail(row, names, row_teams[row["id"]]) for row in rows
        ],
    }


def activity(timeline, battle: list[dict]) -> list[dict]:
    """ISK lost per minute across the whole fleet, by team.

    The sides are the whole fleet's, so the strip keeps its colours while
    the report below is scoped to a window.
    """
    ours = our_characters(timeline.killmails or [])
    teams, _ = assign_sides(battle, ours)
    minutes: dict = {}
    for row in battle:
        minute = parse_time(row["t"]).replace(second=0, microsecond=0)
        team = _team_of(
            teams, _victim_group(row), row["victim"]["character"], ours
        )
        isk = minutes.setdefault(minute, [0] * MAX_TEAMS)
        isk[min(team, MAX_TEAMS - 1)] += row["isk"]
    return [
        {"minute": minute.isoformat(), "isk": isk}
        for minute, isk in sorted(minutes.items())
    ]


def build_window_report(
    timeline, start=None, end=None, sides: str | None = None
):
    """The battle report for every mail from ``start`` to ``end``.

    Without a window it covers the whole fleet: every mail in the snapshot,
    in every system. Sides are worked out from the window's own mails, so a
    group that fought both sides over the night lands where it fought in
    the window. None when the snapshot is empty.
    """
    battle, collected = _battle(timeline)
    if not battle:
        return None
    first, last = parse_time(battle[0]["t"]), parse_time(battle[-1]["t"])
    span_start, span_end = first - WINDOW_PAD, last + WINDOW_PAD
    if start and end and start > end:
        start, end = end, start
    window_start, window_end = start or span_start, end or span_end
    rows = [
        row
        for row in battle
        if window_start <= parse_time(row["t"]) <= window_end
    ]
    times = [parse_time(row["t"]) for row in rows]
    rounds = (timeline.payload or {}).get("rounds") or []
    return {
        "fleet_id": timeline.eve_fleet_id,
        "whole": start is None and end is None,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "start": (min(times) if times else window_start).isoformat(),
        "end": (max(times) if times else window_end).isoformat(),
        "minutes": (
            round((max(times) - min(times)).total_seconds() / 60)
            if times
            else 0
        ),
        "span_start": span_start.isoformat(),
        "span_end": span_end.isoformat(),
        "complete": collected and not any(r.get("partial") for r in rows),
        **_report(timeline, rows, sides),
        "activity": activity(timeline, battle),
        "fights": [
            {
                "start": (parse_time(r["start"]) - WINDOW_PAD).isoformat(),
                "end": (parse_time(r["end"]) + WINDOW_PAD).isoformat(),
            }
            for r in rounds
        ],
    }
