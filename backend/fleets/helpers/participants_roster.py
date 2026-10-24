"""
The people behind a fleet's characters, in the order they joined.

Builds on the per-character ship history ``participants._pilot_ships``
reads:

- Characters fold into one person per account (``EveCharacter.user``).
  The account's primary character names it when it was in fleet, else its
  first character to join. Characters nobody registered are a person each.
- Each character's ship history becomes time segments: a ship from the
  snapshot that saw it until the next snapshot, or until the character was
  last seen. A pilot counts by the hull they flew longest.
- Kills and losses come from the fight timeline's matched killmail rows
  (``EveFleetFightTimeline.killmails``): a kill for every one of our pilots
  on it, a loss for the victim. Without a timeline they are unknown.
- The in-fleet series counts characters in fleet each minute.
- Reship waves the timeline found after the form-up split the fleet into
  parts for the by-ship view.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from eveonline.killmail_classes import is_capsule

CAPSULE_NAME = "Capsule"
STEP = timedelta(minutes=1)
# Reships while the fleet forms up are not a change of plan.
FORM_UP = timedelta(minutes=15)
# Less time than this in a part of the fleet does not count towards it.
MIN_PHASE_PRESENCE = timedelta(minutes=3)


def is_pod(ship_type_id, ship_name) -> bool:
    return is_capsule(ship_type_id) or ship_name == CAPSULE_NAME


@dataclass
class Segment:
    start: datetime
    end: datetime
    ship_type_id: int
    ship_name: str


@dataclass
class Tally:
    """Kills and ship losses per character, with when each loss was."""

    kills: dict = field(default_factory=lambda: defaultdict(int))
    losses: dict = field(default_factory=lambda: defaultdict(list))

    def on_killmail(self, character_id) -> bool:
        return bool(
            self.kills.get(character_id) or self.losses.get(character_id)
        )


def presence(pilot) -> tuple[datetime, datetime]:
    """When a character was first and last seen, over every instance."""
    return (
        min(first for first, _ in pilot["windows"]),
        max(last for _, last in pilot["windows"]),
    )


def segments(pilot) -> list[Segment]:
    """Ships in the order flown, neighbouring snapshots of one hull merged."""
    joined, left = presence(pilot)
    timed = list(zip(pilot["snapshots"], pilot["snapshot_at"]))
    if not timed:
        type_id, name = pilot["members"][-1]
        return [Segment(joined, left, type_id, name)]
    result: list[Segment] = []
    for index, ((type_id, name), at) in enumerate(timed):
        start = min(joined, at) if index == 0 else at
        end = timed[index + 1][1] if index + 1 < len(timed) else left
        end = max(end, start)
        if result and result[-1].ship_type_id == type_id:
            result[-1].end = end
            continue
        result.append(Segment(start, end, type_id, name))
    return result


def longest_hull(
    pilot_segments: list[Segment],
    start: datetime | None = None,
    end: datetime | None = None,
) -> tuple[int, str] | None:
    """The non-capsule hull flown longest, optionally inside a window."""
    flown: dict[tuple[int, str], timedelta] = {}
    for segment in pilot_segments:
        if is_pod(segment.ship_type_id, segment.ship_name):
            continue
        lo = max(segment.start, start) if start else segment.start
        hi = min(segment.end, end) if end else segment.end
        if hi < lo:
            continue
        hull = (segment.ship_type_id, segment.ship_name)
        flown[hull] = flown.get(hull, timedelta(0)) + (hi - lo)
    if not flown:
        return None
    # Ties go to the hull flown first (dicts keep insertion order).
    return max(flown, key=lambda hull: flown[hull])


def tally(rows, start=None, end=None) -> Tally:
    """Kills and losses on the timeline's rows, optionally in a window."""
    # pylint: disable=import-outside-toplevel
    from fleets.helpers.fights.rounds import parse_time

    result = Tally()
    for row in rows or ():
        moment = parse_time(row["t"])
        if (start and moment < start) or (end and moment > end):
            continue
        if row.get("outcome") == "kill":
            for character_id in row.get("pilots") or ():
                result.kills[character_id] += 1
        elif row.get("victim") and not row.get("pod"):
            result.losses[row["victim"]].append(moment)
    return result


def accounts(character_ids) -> tuple[dict[int, object], set[int]]:
    """Each character's account key, and the primary character ids."""
    # pylint: disable=import-outside-toplevel
    from eveonline.models import EveCharacter, EvePlayer

    users = dict(
        EveCharacter.objects.filter(
            character_id__in=character_ids, user__isnull=False
        ).values_list("character_id", "user_id")
    )
    primaries = set(
        EvePlayer.objects.filter(
            user_id__in=set(users.values()),
            primary_character__isnull=False,
        ).values_list("primary_character__character_id", flat=True)
    )
    keys = {
        character_id: users.get(character_id, ("character", character_id))
        for character_id in character_ids
    }
    return keys, primaries


def in_fleet_series(pilots) -> tuple[list[dict], int, datetime | None]:
    """Characters in fleet each minute: change points, peak and its time."""
    spans = [presence(pilot) for pilot in pilots.values()]
    if not spans:
        return [], 0, None
    moment = min(first for first, _ in spans)
    end = max(last for _, last in spans)
    points: list[dict] = []
    peak, peak_at = 0, None
    while moment <= end + STEP:
        count = sum(1 for first, last in spans if first <= moment <= last)
        if not points or points[-1]["count"] != count:
            points.append({"at": moment, "count": count})
        if count > peak:
            peak, peak_at = count, moment
        moment += STEP
    return points, peak, peak_at


def fleet_events(payload) -> list[dict]:
    """Join and reship waves the timeline found, oldest first."""
    # pylint: disable=import-outside-toplevel
    from fleets.helpers.fights.rounds import parse_time

    return [
        {
            "kind": event["kind"],
            "at": parse_time(event["at"]),
            "count": event.get("count") or 0,
            "ships": event.get("ships") or [],
        }
        for event in (payload or {}).get("events") or []
        if event.get("kind") in ("joined", "reship")
    ]


def phase_cuts(events, start: datetime) -> list[datetime]:
    """Reship waves after the form-up: where one part of the fleet ends."""
    return [
        event["at"]
        for event in events
        if event["kind"] == "reship" and event["at"] > start + FORM_UP
    ]


def person_rows(
    pilots, flown_segments, kills: Tally | None, visible, keys, primaries
):
    """
    One row per person in join order, their characters inside it.

    ``keys`` and ``primaries`` come from ``accounts``. Returns
    ``(rows, hidden)``: rows name only characters ``visible`` allows;
    ``hidden`` counts people with no visible character.
    """
    people: dict[object, list[int]] = defaultdict(list)
    for character_id in pilots:
        people[keys[character_id]].append(character_id)

    def character_row(character_id):
        pilot = pilots[character_id]
        joined, left = presence(pilot)
        ships = flown_segments[character_id]
        hull = longest_hull(ships)
        return {
            "character_id": character_id,
            "character_name": pilot["name"],
            "joined": joined,
            "left": left,
            "kills": kills.kills.get(character_id, 0) if kills else None,
            "losses": (
                len(kills.losses.get(character_id, ())) if kills else None
            ),
            "lost_at": (
                list(kills.losses.get(character_id, ())) if kills else []
            ),
            "ship_type_id": hull[0] if hull else ships[-1].ship_type_id,
            "ship_name": hull[1] if hull else ships[-1].ship_name,
            "ships": [
                {
                    "ship_type_id": s.ship_type_id,
                    "ship_name": s.ship_name,
                    "start": s.start,
                    "end": s.end,
                }
                for s in ships
            ],
        }

    rows, hidden = [], 0
    for key, character_ids in people.items():
        shown = [c for c in character_ids if visible(c)]
        if not shown:
            hidden += 1
            continue
        characters = sorted(
            (character_row(c) for c in shown),
            key=lambda c: (
                c["character_id"] not in primaries,
                c["joined"],
                c["character_name"].lower(),
            ),
        )
        lead = characters[0]
        rows.append(
            {
                "character_id": lead["character_id"],
                "character_name": lead["character_name"],
                "registered": not isinstance(key, tuple),
                "joined": min(c["joined"] for c in characters),
                "kills": (
                    sum(c["kills"] for c in characters) if kills else None
                ),
                "losses": (
                    sum(c["losses"] for c in characters) if kills else None
                ),
                "characters": characters,
            }
        )
    rows.sort(key=lambda row: (row["joined"], row["character_name"].lower()))
    return rows, hidden
