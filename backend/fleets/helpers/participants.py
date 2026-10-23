"""
Who flew a fleet, read back from the tracked roster.

Every instance of the fleet counts, so a pilot who was in two instances is
still one pilot. Ship history comes from the append-only ship snapshots;
the member row holds the last ship the poller saw.

- What the fleet flew counts each pilot once, by the hull they flew
  longest that is not a capsule (the member row when no snapshot has one).
- Roles flown look at every hull a pilot was in, so a pilot who reshipped
  into logi counts as logi. Hulls are matched to roles the same way a pilot
  in a live fleet is (``role_coverage.hull_roles``): the fleet's
  composition fit for that hull, else logi from a logi hull group. The fit
  a pilot actually flew is not known, so an off-doctrine links or cyno hull
  is not counted.
- No-shows are ship sign-ups whose character never joined any instance.

An engagement (a round or skirmish of the fight timeline, by its 1-based
position in the timeline's ``rounds``) narrows all of this to the pilots in
fleet during it, give or take a minute, each by the hull they were in at
the time: the latest non-capsule ship seen by the end of it.

The whole-fleet view also has the people behind the characters in join
order, the in-fleet count over time and the fleet split into parts at its
reship waves (``participants_roster``).

For viewers who are not Strategic FCs every pilot who flew a sensitive hull
(fleets.helpers.opsec) is left out entirely, and so is the cyno row.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from django.utils.dateparse import parse_datetime
from eveuniverse.models import EveType
from eveonline.killmail_classes import is_capsule
from fittings.models import EveFitting

from fleets.helpers.doctrine_flown import (
    doctrine_hulls,
    doctrine_segment,
    pick_doctrine,
)
from fleets.helpers.opsec import sensitive_hull_ids, sensitive_pilot_ids
from fleets.helpers import participants_roster as roster
from fleets.helpers.presence import (
    JOIN_GRACE,
    LAST_SEEN_GRACE,
    member_window,
)
from fleets.helpers.role_coverage import hull_roles

CAPSULE_NAME = "Capsule"

# (key, label, FitRoles predicate), in display order.
ROLES_FLOWN = (
    ("logi", "Logistics", lambda roles: roles.logi),
    ("links", "Links", lambda roles: roles.links),
    ("cyno", "Cyno", lambda roles: roles.cyno),
)
OPSEC_ROLES = frozenset({"cyno"})

# Pilots count towards an engagement when in fleet this close to it.
ENGAGEMENT_SLACK = timedelta(minutes=1)


class EngagementNotFound(LookupError):
    """No round or skirmish at that position of the fleet's fight timeline."""


@dataclass
class _Flown:
    """What one pilot flew over the stretch being reported."""

    hull: tuple[int, str]  # what the pilot counts as
    hulls: list[tuple[int, str]]  # every non-capsule hull, for roles
    changed: bool
    podded: bool


def _is_pod(ship_type_id, ship_name) -> bool:
    return is_capsule(ship_type_id) or ship_name == CAPSULE_NAME


def _parse_time(value: str) -> datetime:
    moment = parse_datetime(value)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


def _pilot_ships(fleet) -> dict[int, dict]:
    """
    Per character: name, ship snapshots in order with when each was taken,
    member rows in order and the presence window of each row.
    """
    # pylint: disable=import-outside-toplevel
    from fleets.models import (
        EveFleetInstanceMember,
        EveFleetInstanceMemberShipSnapshot,
    )

    pilots: dict[int, dict] = {}
    members = EveFleetInstanceMember.objects.filter(
        eve_fleet_instance__eve_fleet=fleet
    ).order_by("eve_fleet_instance__start_time", "updated_at", "id")
    for (
        character_id,
        character_name,
        ship_type_id,
        ship_name,
        join_time,
        created_at,
        updated_at,
    ) in members.values_list(
        "character_id",
        "character_name",
        "ship_type_id",
        "ship_name",
        "join_time",
        "created_at",
        "updated_at",
    ):
        pilot = pilots.setdefault(
            character_id,
            {
                "name": "",
                "snapshots": [],
                "snapshot_at": [],
                "members": [],
                "windows": [],
            },
        )
        pilot["name"] = character_name
        pilot["members"].append((ship_type_id, ship_name))
        pilot["windows"].append(
            member_window(join_time, created_at, updated_at)
        )

    snapshots = EveFleetInstanceMemberShipSnapshot.objects.filter(
        member__eve_fleet_instance__eve_fleet=fleet
    ).order_by("created_at", "id")
    for (
        character_id,
        ship_type_id,
        ship_name,
        created_at,
    ) in snapshots.values_list(
        "member__character_id", "ship_type_id", "ship_name", "created_at"
    ):
        pilots[character_id]["snapshots"].append((ship_type_id, ship_name))
        pilots[character_id]["snapshot_at"].append(created_at)
    return pilots


def _first_ship(pilot) -> tuple[int, str]:
    for ship in pilot["snapshots"]:
        if not _is_pod(*ship):
            return ship
    for ship in pilot["members"]:
        if not _is_pod(*ship):
            return ship
    return pilot["members"][-1]


def _hulls_flown(pilot) -> list[tuple[int, str]]:
    """Every non-capsule hull, in the order first seen."""
    seen = {}
    for ship in pilot["snapshots"] + pilot["members"]:
        if not _is_pod(*ship):
            seen.setdefault(ship[0], ship)
    return list(seen.values())


def _whole_fleet(pilot) -> _Flown:
    return _Flown(
        hull=roster.longest_hull(roster.segments(pilot)) or _first_ship(pilot),
        hulls=_hulls_flown(pilot),
        changed=len({type_id for type_id, _ in pilot["snapshots"]}) > 1,
        podded=_is_pod(*pilot["members"][-1]),
    )


def _present(pilot, start: datetime, end: datetime) -> bool:
    """In fleet at any moment of ``[start, end]``, with the polling grace
    ``presence.was_present`` allows."""
    return any(
        first_seen - JOIN_GRACE <= end and last_seen + LAST_SEEN_GRACE >= start
        for first_seen, last_seen in pilot["windows"]
    )


def _during(pilot, start: datetime, end: datetime) -> _Flown:
    """What a pilot flew between ``start`` and ``end``."""
    timed = list(zip(pilot["snapshots"], pilot["snapshot_at"]))
    by_end = [ship for ship, at in timed if at <= end]
    hull = next(
        (ship for ship in reversed(by_end) if not _is_pod(*ship)), None
    ) or _first_ship(pilot)
    # The ship they were in as the window opened, then every change in it.
    before = [ship for ship, at in timed if at <= start]
    window = before[-1:] + [ship for ship, at in timed if start < at <= end]
    if not window:
        return _Flown(
            hull=hull,
            hulls=[] if _is_pod(*hull) else [hull],
            changed=False,
            podded=_is_pod(*hull),
        )
    hulls = {}
    for ship in window:
        if not _is_pod(*ship):
            hulls.setdefault(ship[0], ship)
    return _Flown(
        hull=hull,
        hulls=list(hulls.values()),
        changed=len({type_id for type_id, _ in window}) > 1,
        podded=_is_pod(*window[-1]),
    )


def _roles_flown(
    pilots, flown: dict[int, _Flown], roles_by_hull, visible, opsec
) -> list[dict]:
    rows = []
    for key, label, fills in ROLES_FLOWN:
        if opsec and key in OPSEC_ROLES:
            continue
        flyers = []
        for character_id, record in flown.items():
            # The pilot's first hull that fills the role stands for them.
            hull = next(
                (h for h in record.hulls if fills(roles_by_hull[h[0]])), None
            )
            if hull:
                flyers.append((character_id, hull))
        hull_counts = Counter(name for _, (_, name) in flyers)
        rows.append(
            {
                "role": key,
                "label": label,
                "count": len(flyers),
                "hulls": [
                    {"ship_name": name, "count": count}
                    for name, count in sorted(
                        hull_counts.items(), key=lambda kv: (-kv[1], kv[0])
                    )
                ],
                "pilots": sorted(
                    (
                        {
                            "character_id": character_id,
                            "character_name": pilots[character_id]["name"],
                            "ship_name": name,
                        }
                        for character_id, (_, name) in flyers
                        if visible(character_id)
                    ),
                    key=lambda row: row["character_name"].lower(),
                ),
            }
        )
    return rows


def _flew(pilots, flown: dict[int, _Flown], visible, kills=None) -> list[dict]:
    """One row per hull, each pilot by the hull they count as."""
    rows: dict[int, dict] = {}
    for character_id, record in flown.items():
        type_id, name = record.hull
        row = rows.setdefault(
            type_id,
            {
                "ship_type_id": type_id,
                "ship_name": name,
                "count": 0,
                "pilots": [],
            },
        )
        row["count"] += 1
        if visible(character_id):
            row["pilots"].append(
                {
                    "character_id": character_id,
                    "character_name": pilots[character_id]["name"],
                    "kills": (
                        kills.kills.get(character_id, 0) if kills else None
                    ),
                    "losses": (
                        len(kills.losses.get(character_id, ()))
                        if kills
                        else None
                    ),
                }
            )
    for row in rows.values():
        row["pilots"].sort(key=lambda p: p["character_name"].lower())
    return sorted(
        rows.values(), key=lambda row: (-row["count"], row["ship_name"])
    )


def _timeline(fleet) -> tuple[dict | None, list]:
    """The fight timeline's payload and matched killmail rows."""
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetFightTimeline

    row = (
        EveFleetFightTimeline.objects.filter(eve_fleet=fleet)
        .values_list("payload", "killmails")
        .first()
    )
    if not row or not row[0]:
        return None, []
    return row[0], row[1] or []


def fleet_engagements(payload) -> list[dict] | None:
    """
    The fight timeline's rounds and skirmishes with their 1-based position,
    or None when the fleet has no timeline yet.
    """
    if not payload:
        return None
    return [
        {
            "position": position,
            "kind": summary.get("kind"),
            "number": summary.get("number"),
            "start": summary["start"],
            "end": summary["end"],
            "kills": summary.get("ships_destroyed") or 0,
            "losses": summary.get("ships_lost") or 0,
            "systems": [
                system.get("name") for system in summary.get("systems") or []
            ],
            "against": [
                group.get("name") for group in summary.get("hostiles") or []
            ],
        }
        for position, summary in enumerate(payload.get("rounds") or [], 1)
    ]


def _window(engagement: dict) -> tuple[datetime, datetime]:
    return (
        _parse_time(engagement["start"]) - ENGAGEMENT_SLACK,
        _parse_time(engagement["end"]) + ENGAGEMENT_SLACK,
    )


def _hulls_at(pilots, start, end) -> dict[int, tuple[int, str]]:
    """Non-capsule hull of every pilot in fleet during the window."""
    hulls = {}
    for character_id, pilot in pilots.items():
        if not _present(pilot, start, end):
            continue
        hull = _during(pilot, start, end).hull
        if not _is_pod(*hull):
            hulls[character_id] = hull
    return hulls


def _tracking_span(fleet) -> tuple[datetime | None, datetime | None]:
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetInstance

    rows = list(
        EveFleetInstance.objects.filter(eve_fleet=fleet).values_list(
            "start_time", "end_time", "last_updated"
        )
    )
    if not rows:
        return None, None
    ends = [end or updated for _, end, updated in rows if end or updated]
    return min(start for start, _, _ in rows), max(ends) if ends else None


def _doctrine_flown(fleet, pilots, rounds) -> list[dict]:
    """
    One segment per round; neighbouring rounds on the same doctrine merge.
    A fleet with a timeline but no rounds gets one segment for the whole
    fleet, by each pilot's first hull.
    """
    if rounds is None or not pilots:
        return []
    doctrines = doctrine_hulls()
    if not rounds:
        hulls = {
            character_id: _first_ship(pilot)
            for character_id, pilot in pilots.items()
            if not _is_pod(*_first_ship(pilot))
        }
        start, end = _tracking_span(fleet)
        return [
            {
                "start": start,
                "end": end,
                "positions": [],
                **doctrine_segment(
                    hulls,
                    doctrines,
                    pick_doctrine(hulls, doctrines, fleet.doctrine_id),
                ),
            }
        ]

    segments: list[dict] = []
    for engagement in rounds:
        hulls = _hulls_at(pilots, *_window(engagement))
        doctrine_id = pick_doctrine(hulls, doctrines, fleet.doctrine_id)
        if segments and segments[-1]["doctrine_id"] == doctrine_id:
            last: dict = segments[-1]
            last["end"] = engagement["end"]
            last["positions"].append(engagement["position"])
            # A pilot in several merged rounds counts by their latest hull.
            last["hulls"].update(hulls)
            continue
        segments.append(
            {
                "start": engagement["start"],
                "end": engagement["end"],
                "positions": [engagement["position"]],
                "doctrine_id": doctrine_id,
                "hulls": dict(hulls),
            }
        )
    return [
        {
            "start": segment["start"],
            "end": segment["end"],
            "positions": segment["positions"],
            **doctrine_segment(
                segment["hulls"], doctrines, segment["doctrine_id"]
            ),
        }
        for segment in segments
    ]


def fleet_no_shows(
    fleet, member_ids: set[int], hidden_ids: frozenset[int] = frozenset()
) -> dict:
    """
    Ship sign-ups whose character never joined the fleet.

    ``hidden_ids`` (pilots the viewer may not see) still count as having
    joined, but not towards joined_without_signing_up.
    """
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetShipVolunteer

    volunteers = list(
        EveFleetShipVolunteer.objects.filter(eve_fleet=fleet)
        .select_related("fitting", "fleet_fitting")
        .order_by("character_name", "id")
    )
    hull_names = dict(
        EveType.objects.filter(
            id__in={v.target_ship_id for v in volunteers}
        ).values_list("id", "name")
    )
    volunteer_ids = {v.character_id for v in volunteers}
    return {
        "signed_up": len(volunteer_ids),
        "joined_without_signing_up": len(
            member_ids - volunteer_ids - set(hidden_ids)
        ),
        "no_shows": [
            {
                "character_id": v.character_id,
                "character_name": v.character_name,
                "ship_type_id": v.target_ship_id,
                "ship_name": hull_names.get(v.target_ship_id)
                or EveFitting.ship_name_from_eft(v.target_eft or ""),
            }
            for v in volunteers
            if v.character_id not in member_ids
        ],
    }


def fleet_participants(
    fleet,
    visible=lambda character_id: True,
    *,
    engagement: int | None = None,
    opsec: bool = False,
) -> dict:
    """
    Hulls flown, reships, pods, roles flown and doctrine flown for a fleet's
    tracked pilots.

    ``visible`` limits which pilots are named; the counts cover everyone.
    ``engagement`` narrows to one round of the fight timeline (raises
    EngagementNotFound for a missing position or a skirmish). ``opsec``
    leaves out every pilot who flew a sensitive hull, and the cyno row.
    """
    pilots = _pilot_ships(fleet)
    member_ids = set(pilots)

    whole = {
        character_id: _whole_fleet(pilot)
        for character_id, pilot in pilots.items()
    }
    roles_by_hull = hull_roles(
        fleet,
        {type_id for record in whole.values() for type_id, _ in record.hulls},
    )
    hidden: set[int] = set()
    if opsec:
        sensitive = sensitive_hull_ids(fleet, roles_by_hull, roles_by_hull)
        hidden = sensitive_pilot_ids(
            {
                character_id: [type_id for type_id, _ in record.hulls]
                for character_id, record in whole.items()
            },
            sensitive,
        )
        pilots = {
            character_id: pilot
            for character_id, pilot in pilots.items()
            if character_id not in hidden
        }

    payload, killmails = _timeline(fleet)
    timeline = fleet_engagements(payload)
    rounds = [e for e in timeline or [] if e["kind"] == "round"]
    chosen = None
    if engagement is None:
        flown = {character_id: whole[character_id] for character_id in pilots}
        kills = roster.tally(killmails) if payload else None
    else:
        chosen = next(
            (e for e in timeline or [] if e["position"] == engagement), None
        )
        if chosen is None:
            raise EngagementNotFound(engagement)
        start, end = _window(chosen)
        flown = {
            character_id: _during(pilot, start, end)
            for character_id, pilot in pilots.items()
            if _present(pilot, start, end)
        }
        kills = roster.tally(killmails, start, end)

    keys, primaries = roster.accounts(list(pilots))
    in_fleet, peak, peak_at = roster.in_fleet_series(pilots)
    events = roster.fleet_events(payload)
    on_killmail = (
        {c for c in flown if kills.on_killmail(c)} if kills else set()
    )
    whole_view = {}
    if engagement is None:
        flown_segments = {
            character_id: roster.segments(pilot)
            for character_id, pilot in pilots.items()
        }
        rows, hidden_people = roster.person_rows(
            pilots, flown_segments, kills, visible, keys, primaries
        )
        whole_view = {
            "roster": rows,
            "hidden_pilots": hidden_people,
            "phases": _phases(
                pilots, flown_segments, events, in_fleet, visible
            ),
        }

    return {
        "pilots": len(flown),
        "characters": len(flown),
        "people": len({keys[c] for c in flown}),
        "on_killmail": len(on_killmail) if kills else None,
        "people_on_killmail": (
            len({keys[c] for c in on_killmail}) if kills else None
        ),
        "flew": _flew(pilots, flown, visible, kills),
        "changed_ship": sum(1 for record in flown.values() if record.changed),
        "ended_in_pod": sum(1 for record in flown.values() if record.podded),
        "roles_flown": _roles_flown(
            pilots, flown, roles_by_hull, visible, opsec
        ),
        "engagements": [
            {key: e[key] for key in ("position", "number", "start", "end")}
            for e in rounds
        ],
        "fights": [
            {
                key: e[key]
                for key in (
                    "position",
                    "kind",
                    "number",
                    "start",
                    "end",
                    "kills",
                    "losses",
                )
            }
            for e in timeline or []
        ],
        "engagement": engagement,
        "fight": chosen,
        "in_fleet": in_fleet,
        "peak": peak,
        "peak_at": peak_at,
        "fleet_events": events,
        "doctrine_flown": _doctrine_flown(
            fleet, pilots, None if timeline is None else rounds
        ),
        "opsec_filtered": opsec,
        "member_ids": member_ids,
        "hidden_ids": hidden,
        **whole_view,
    }


def _phases(pilots, flown_segments, events, in_fleet, visible) -> list[dict]:
    """
    The fleet split at its reship waves: each pilot in a part counts once,
    by the hull they flew longest in it.
    """
    if not pilots:
        return []
    spans = {c: roster.presence(pilot) for c, pilot in pilots.items()}
    start = min(first for first, _ in spans.values())
    end = max(last for _, last in spans.values())
    cuts = [start, *roster.phase_cuts(events, start), end]
    phases = []
    for lo, hi in zip(cuts, cuts[1:]):
        flown: dict[int, _Flown] = {}
        for character_id, (first, last) in spans.items():
            # Leaving just after a cut is not flying in the next part.
            if min(last, hi) - max(first, lo) < roster.MIN_PHASE_PRESENCE:
                continue
            hull = roster.longest_hull(flown_segments[character_id], lo, hi)
            if hull is None:
                continue
            flown[character_id] = _Flown(
                hull=hull, hulls=[hull], changed=False, podded=False
            )
        # The count as the part opens, then every change inside it.
        before = [p["count"] for p in in_fleet if p["at"] <= lo][-1:]
        inside = [p["count"] for p in in_fleet if lo < p["at"] <= hi]
        peak = max(before + inside, default=0)
        phases.append(
            {
                "start": lo,
                "end": hi,
                "characters": len(flown),
                "peak": peak,
                "hulls": _flew(pilots, flown, visible),
            }
        )
    return phases
