"""
The desktop app's fleet window, in one cached read.

Every signed-in desktop app polls this every 30 s (the fleet poller's pace),
so the work is split in two:

- Fleet-wide data (fleet, pilots in fleet now, doctrine counts, role gaps,
  kill totals) is built once per fleet and cached until the poller stamps
  the instance again, the fleet is edited, or a pilot changes their ship
  sign-up. A fleet of 40 desktop apps costs one build per poll, not 40.
- The viewer's part (their own characters, their last loss, and for the FC
  only the roster and who needs a nudge) is a cheap filter over that.

"Which fleet am I in?" reads a small index of open fleets and the
characters in each, cached for everyone, so the common answer ("none")
costs one query for the caller's character ids.
"""

from datetime import datetime, timedelta

from django.db.models import Q
from django.utils import timezone

from eveonline.helpers.corporations.safe_cache import (
    cache_delete,
    cache_get,
    cache_set,
)
from eveonline.helpers.characters.identity import owner_user_ids
from eveonline.models import EveCharacter
from eveonline.killmail_classes import CAPSULE_TYPE_IDS
from feed.helpers.fleet_kills import fleet_kill_report
from fleets.helpers.composition import fleet_composition
from fleets.helpers.role_coverage import PRESENT_SLACK

SHARED_CACHE_SECONDS = 60
INDEX_CACHE_SECONDS = 15
INDEX_KEY = "fleets:window:index"

# A poller that has not stamped an open instance for this long has stopped;
# its member rows no longer say who is in fleet.
STALE_POLL = timedelta(minutes=15)
# The FC keeps the after-action view this long after the fleet closes.
AFTER_ACTION = timedelta(hours=3)
# A loss shows on the pilot's window for this long.
RECENT_LOSS = timedelta(minutes=15)
# The FC's kill feed: newest killmails, kills and losses together.
FEED_LIMIT = 40
# The Fights view: groups named per round, bars across the latest round.
FIGHT_HOSTILES = 3
FIGHT_BINS = 30

TYPE_LABELS = {
    "strategic": "Strategic",
    "non_strategic": "Non-Strategic",
    "training": "Training",
    "npsi": "NPSI",
    "standing": "Standing",
    "gang": "Gang",
}

# Doctrine roles a fit can fill, in the order the window lists them.
FIT_ROLES = ("logi", "links", "cyno")
FIT_ROLE_LABELS = {"logi": "Logi", "links": "Links", "cyno": "Cyno"}
DOCTRINE_ROLE_LABELS = {
    "primary": "Mainline",
    "secondary": "Secondary",
    "support": "Support",
    "utility": "Utility",
}


def _role_label(entry) -> str:
    """What the ship does: its fit role when it has one, else its slot."""
    for role in FIT_ROLES:
        if getattr(entry.roles, role):
            return FIT_ROLE_LABELS[role]
    return DOCTRINE_ROLE_LABELS.get(entry.role, entry.role.title())


def _shared_key(fleet_id: int) -> str:
    return f"fleets:window:fleet:{fleet_id}"


def forget_fleet_window(fleet_id: int) -> None:
    """Drop the cached fleet-wide part, e.g. after a ship sign-up changes."""
    cache_delete(_shared_key(fleet_id))


# ---------------------------------------------------------------- index


def _iso(value):
    return value.isoformat() if value else None


def _fleet_index() -> list[dict]:
    """Open (and recently closed) fleet instances and who is in them."""
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetInstance, EveFleetInstanceMember

    rows = cache_get(INDEX_KEY)
    if rows is not None:
        return rows

    now = timezone.now()
    instances = list(
        EveFleetInstance.objects.filter(
            Q(end_time__isnull=True) | Q(end_time__gte=now - AFTER_ACTION)
        )
        .order_by("-start_time")
        .values(
            "id",
            "eve_fleet_id",
            "eve_fleet__created_by_id",
            "end_time",
            "last_updated",
        )
    )
    polled = {
        row["id"]: row["last_updated"]
        for row in instances
        if row["end_time"] is None
        and row["last_updated"]
        and row["last_updated"] >= now - STALE_POLL
    }
    present = {}
    if polled:
        members = EveFleetInstanceMember.objects.filter(
            eve_fleet_instance_id__in=polled.keys(),
            updated_at__gte=min(polled.values()) - PRESENT_SLACK,
        ).values_list("eve_fleet_instance_id", "character_id", "updated_at")
        for instance_id, character_id, updated_at in members:
            if updated_at >= polled[instance_id] - PRESENT_SLACK:
                present.setdefault(instance_id, []).append(character_id)

    rows = [
        {
            "fleet_id": row["eve_fleet_id"],
            "fc_user_id": row["eve_fleet__created_by_id"],
            "ended": row["end_time"] is not None,
            "characters": present.get(row["id"], []),
        }
        for row in instances
    ]
    cache_set(INDEX_KEY, rows, INDEX_CACHE_SECONDS)
    return rows


def _character_ids(user) -> set[int]:
    return set(
        EveCharacter.objects.filter(user=user).values_list(
            "character_id", flat=True
        )
    )


def current_window_fleet_id(user) -> int | None:
    """The fleet the user commands or flies in now, else one they just ran."""
    index = _fleet_index()
    live = [row for row in index if not row["ended"]]
    for row in live:
        if row["fc_user_id"] == user.id:
            return row["fleet_id"]
    if any(row["characters"] for row in live):
        mine = _character_ids(user)
        for row in live:
            if mine.intersection(row["characters"]):
                return row["fleet_id"]
    for row in index:
        if row["ended"] and row["fc_user_id"] == user.id:
            return row["fleet_id"]
    return None


# ---------------------------------------------------------------- fleet-wide


def _instance(fleet):
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetInstance

    return (
        EveFleetInstance.objects.filter(eve_fleet=fleet)
        .order_by("-start_time")
        .first()
    )


def _stamp(fleet, instance) -> list:
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetFightTimeline

    fights_at = (
        EveFleetFightTimeline.objects.filter(eve_fleet=fleet)
        .values_list("computed_at", flat=True)
        .first()
    )
    return [
        _iso(fleet.updated_at),
        instance.id if instance else None,
        _iso(instance.last_updated) if instance else None,
        _iso(instance.end_time) if instance else None,
        _iso(fights_at),
    ]


def _members(instance) -> list:
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetInstanceMember

    if instance is None:
        return []
    members = EveFleetInstanceMember.objects.filter(
        eve_fleet_instance=instance
    )
    if instance.end_time is None:
        if not instance.last_updated:
            return []
        members = members.filter(
            updated_at__gte=instance.last_updated - PRESENT_SLACK
        )
    return list(
        members.values(
            "character_id",
            "character_name",
            "ship_type_id",
            "ship_name",
            "solar_system_id",
            "solar_system_name",
            "station_id",
        )
    )


def _fc_system(instance, members, fc_character_id):
    """Where the fleet is: the boss, else the FC, else the busiest system."""
    by_character = {m["character_id"]: m for m in members}
    for character_id in (
        instance.boss_id if instance else None,
        fc_character_id,
    ):
        member = by_character.get(character_id)
        if member:
            return member["solar_system_id"], member["solar_system_name"]
    counts = {}
    for member in members:
        system = (member["solar_system_id"], member["solar_system_name"])
        counts[system] = counts.get(system, 0) + 1
    if not counts:
        return None, None
    return max(counts, key=counts.get)


def _absent_volunteers(fleet, pilots) -> list[str]:
    """Signed up but not in fleet, on any of their characters.

    A pilot who signed up on their main and flies an alt is in fleet.
    """
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetShipVolunteer

    volunteers = list(
        EveFleetShipVolunteer.objects.filter(eve_fleet=fleet)
        .order_by("character_name")
        .values_list("character_id", "character_name")
    )
    if not volunteers:
        return []
    in_fleet = {p["character_id"] for p in pilots}
    owners = owner_user_ids(in_fleet | {cid for cid, _ in volunteers})
    users_in_fleet = {owners[cid] for cid in in_fleet if cid in owners}
    absent, seen = [], set()
    for character_id, name in volunteers:
        owner = owners.get(character_id)
        if character_id in in_fleet or (owner and owner in users_in_fleet):
            continue
        if (owner or character_id) in seen:
            continue
        seen.add(owner or character_id)
        absent.append(name)
    return absent


def _feed_rows(report) -> list[dict]:
    return [
        {
            "killmail_id": row["killmail_id"],
            "killmail_time": row["killmail_time"],
            "outcome": row["outcome"],
            "ship_type_id": row.get("victim_ship_type_id"),
            "ship_name": row.get("victim_ship_name") or "",
            "victim_name": row.get("victim_character_name") or "",
            "isk_value": row.get("isk_value") or 0,
            "solar_system_name": row.get("solar_system_name") or "",
            "fleet_pilots": row.get("fleet_pilots") or 0,
            "capsule": bool(row.get("is_capsule")),
        }
        for row in report["killmails"][:FEED_LIMIT]
    ]


def _volunteer_keys(fleet) -> dict[int, str]:
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetShipVolunteer

    # Off-doctrine hulls key as "s:<type id>" and match no doctrine row.
    return {
        volunteer.character_id: volunteer.target_key
        for volunteer in EveFleetShipVolunteer.objects.filter(
            eve_fleet=fleet
        ).only(
            "character_id", "fitting_id", "fleet_fitting_id", "ship_type_id"
        )
    }


def _ships_and_roles(composition, pilots, volunteers, live):
    """Doctrine rows (flying / signed up) and which fit roles are filled."""
    by_hull = {}
    for entry in composition:
        by_hull.setdefault(entry.ship_id, entry)
    flying = {}
    for pilot in pilots:
        entry = by_hull.get(pilot["ship_type_id"])
        if entry is not None:
            flying[entry.key] = flying.get(entry.key, 0) + 1
    signed_up = {}
    for key in volunteers.values():
        signed_up[key] = signed_up.get(key, 0) + 1

    ships = [
        {
            "key": entry.key,
            "name": entry.name,
            "ship_type_id": entry.ship_id,
            "ship_name": entry.ship_name or entry.name,
            "role": entry.role,
            "role_label": _role_label(entry),
            "flying": flying.get(entry.key, 0),
            "signed_up": signed_up.get(entry.key, 0),
        }
        for entry in composition
    ]

    # A role is only listed when a fit in the doctrine fills it; it is
    # covered by a pilot in such a fit (in fleet once live, else signed up).
    filled = flying if live else signed_up
    roles = []
    for role in FIT_ROLES:
        entries = [e for e in composition if getattr(e.roles, role)]
        if entries:
            roles.append(
                {
                    "role": role,
                    "covered": any(filled.get(e.key) for e in entries),
                }
            )
    return ships, roles


def _loss_rows(report) -> list[dict]:
    return [
        {
            "killmail_id": row["killmail_id"],
            "killmail_time": row["killmail_time"],
            "victim_character_id": row.get("victim_character_id"),
            "ship_type_id": row.get("victim_ship_type_id"),
            "ship_name": row.get("victim_ship_name") or "",
            "isk_value": row.get("isk_value") or 0,
            "solar_system_name": row.get("solar_system_name") or "",
        }
        for row in report["killmails"]
        if row["outcome"] == "loss" and not row.get("is_capsule")
    ]


def _compact_round(summary: dict) -> dict:
    return {
        "kind": summary["kind"],
        "number": summary["number"],
        "start": summary["start"],
        "end": summary["end"],
        "minutes": summary["minutes"],
        "kills": summary["ships_destroyed"],
        "losses": summary["ships_lost"],
        "isk_destroyed": summary["isk_destroyed"],
        "isk_lost": summary["isk_lost"],
        "efficiency": summary["efficiency"],
        "fighting": summary["fighting"],
        "systems": [system["name"] for system in summary["systems"]],
        "hostiles": [
            {"name": hostile["name"], "pilots": hostile["pilots"]}
            for hostile in summary["hostiles"][:FIGHT_HOSTILES]
            if hostile["pilots"]
        ],
    }


def _round_bins(summary: dict, now: datetime) -> list:
    """Ships killed and lost per minute across one round."""
    start = datetime.fromisoformat(summary["start"])
    end = (
        now if summary["fighting"] else datetime.fromisoformat(summary["end"])
    )
    count = max(1, int((end - start).total_seconds() // 60) + 1)
    bins = [[0, 0] for _ in range(min(count, FIGHT_BINS))]
    for row in summary["killmails"]:
        if row["pod"]:
            continue
        minute = int(
            (datetime.fromisoformat(row["time"]) - start).total_seconds() // 60
        )
        index = min(len(bins) - 1, minute * len(bins) // count)
        bins[index][0 if row["outcome"] == "kill" else 1] += 1
    return bins


def _fights(fleet) -> dict | None:
    """The fleet's rounds, for the Fights view: the latest one in full."""
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetFightTimeline

    timeline = EveFleetFightTimeline.objects.filter(eve_fleet=fleet).first()
    payload = timeline.payload if timeline else None
    if not payload or not payload.get("rounds"):
        return None
    rounds = payload["rounds"]
    latest = rounds[-1]
    return {
        "round_count": payload["round_count"],
        "skirmish_count": payload["skirmish_count"],
        "latest": {
            **_compact_round(latest),
            "bins": _round_bins(latest, timezone.now()),
        },
        "earlier": [_compact_round(r) for r in reversed(rounds[:-1])],
    }


def _build_shared(fleet, instance) -> dict:
    # pylint: disable=import-outside-toplevel
    from srp.helpers import srp_program_amounts
    from srp.models import EveFleetShipReimbursement

    fc = fleet.fleet_commander
    members = _members(instance)
    composition = fleet_composition(fleet)
    hulls = {}
    for entry in composition:
        hulls.setdefault(entry.ship_id, entry.key)
    live = bool(instance and instance.end_time is None)
    system_id, system_name = _fc_system(
        instance, members, fc.character_id if fc else None
    )

    pilots = [
        {
            "character_id": m["character_id"],
            "character_name": m["character_name"],
            "ship_type_id": m["ship_type_id"],
            "ship_name": m["ship_name"],
            "solar_system_id": m["solar_system_id"],
            "solar_system_name": m["solar_system_name"],
            "docked": m["station_id"] is not None,
            "doctrine": m["ship_type_id"] in hulls,
            "capsule": m["ship_type_id"] in CAPSULE_TYPE_IDS,
        }
        for m in members
    ]
    pilots.sort(
        key=lambda p: (
            p["solar_system_id"] != system_id,
            p["solar_system_name"],
            p["character_name"].lower(),
        )
    )
    volunteers = _volunteer_keys(fleet)
    ships, roles = _ships_and_roles(
        composition, pilots if live else [], volunteers, live
    )

    report = (
        fleet_kill_report(fleet)
        if instance
        else {
            "killmails": [],
            "ships_destroyed": 0,
            "ships_lost": 0,
            "isk_destroyed": 0,
            "isk_lost": 0,
        }
    )
    losses = _loss_rows(report)
    srp_killmails = set(
        EveFleetShipReimbursement.objects.filter(fleet=fleet)
        .exclude(status="withdrawn")
        .values_list("killmail_id", flat=True)
    )

    after_action = None
    if instance and instance.end_time:
        after_action = {
            "pilots": len(pilots),
            "duration_seconds": int(
                (instance.end_time - instance.start_time).total_seconds()
            ),
            "losses": len(losses),
            "srp_filed": sum(
                1 for loss in losses if loss["killmail_id"] in srp_killmails
            ),
            "aar_link": fleet.aar_link or None,
        }

    return {
        "fleet": {
            "id": fleet.id,
            "type": fleet.type,
            "type_label": TYPE_LABELS.get(fleet.type, fleet.type),
            "title": (
                fleet.doctrine.name
                if fleet.doctrine
                else TYPE_LABELS.get(fleet.type, "Fleet") + " fleet"
            ),
            "description": fleet.description or "",
            "doctrine_name": fleet.doctrine.name if fleet.doctrine else None,
            "location_name": (
                fleet.location.location_name if fleet.location else None
            ),
            "location_system_id": (
                fleet.location.solar_system_id if fleet.location else None
            ),
            "location_system_name": (
                fleet.location.solar_system_name if fleet.location else None
            ),
            "start_time": _iso(fleet.start_time),
            "status": fleet.status,
            "live": live,
            "started_at": _iso(instance.start_time) if instance else None,
            "ended_at": _iso(instance.end_time) if instance else None,
            "fc_character_id": fc.character_id if fc else None,
            "fc_name": fc.character_name if fc else None,
            "fc_system_id": system_id,
            "fc_system_name": system_name,
        },
        "fc_user_id": fleet.created_by_id,
        "boss_id": instance.boss_id if instance else None,
        "counts": {
            "in_fleet": len(pilots) if live else 0,
            "with_fc": (
                sum(1 for p in pilots if p["solar_system_id"] == system_id)
                if live
                else 0
            ),
            "kills": report["ships_destroyed"],
            "losses": report["ships_lost"],
            "isk_destroyed": report["isk_destroyed"],
            "isk_lost": report["isk_lost"],
        },
        "ships": ships,
        "roles": roles,
        "pilots": pilots,
        "volunteers": volunteers,
        "losses": losses,
        "feed": _feed_rows(report),
        "absent_volunteers": (
            _absent_volunteers(fleet, pilots) if live else []
        ),
        "srp_killmails": sorted(srp_killmails),
        # Hulls among the losses that SRP pays for (the loss card's File SRP).
        "srp_covered_types": sorted(
            srp_program_amounts(
                {
                    loss["ship_type_id"]
                    for loss in losses
                    if loss["ship_type_id"]
                }
            )
        ),
        "after_action": after_action,
        "fights": _fights(fleet) if instance else None,
    }


def shared_fleet_window(fleet) -> dict:
    """The fleet-wide part, rebuilt only when something it reads changed."""
    instance = _instance(fleet)
    stamp = _stamp(fleet, instance)
    cached = cache_get(_shared_key(fleet.id))
    if cached is not None and cached["stamp"] == stamp:
        return cached["data"]
    data = _build_shared(fleet, instance)
    cache_set(
        _shared_key(fleet.id),
        {"stamp": stamp, "data": data},
        SHARED_CACHE_SECONDS,
    )
    return data


# ---------------------------------------------------------------- viewer


def _needs(shared) -> list[dict]:
    """What the fleet is short of: signed-up hulls not in fleet, role gaps."""
    if not shared["fleet"]["live"]:
        return []
    needs = [
        {
            "kind": "ship",
            "count": ship["signed_up"] - ship["flying"],
            "label": ship["ship_name"],
            "ship_type_id": ship["ship_type_id"],
        }
        for ship in shared["ships"]
        if ship["signed_up"] > ship["flying"]
    ]
    needs += [
        {"kind": "role", "count": 1, "label": role["role"]}
        for role in shared["roles"]
        if not role["covered"]
    ]
    return needs


def _attention(shared) -> list[dict]:
    """Pilots the FC may want to nudge, one group per reason."""
    system_id = shared["fleet"]["fc_system_id"]
    groups = {
        "capsule": [],
        "off_doctrine": [],
        "docked": [],
        "away": [],
        "not_in_fleet": [],
    }
    for pilot in shared["pilots"]:
        if pilot["capsule"]:
            reason = "capsule"
        elif not pilot["doctrine"] and shared["ships"]:
            reason = "off_doctrine"
        elif pilot["docked"]:
            reason = "docked"
        elif pilot["solar_system_id"] != system_id:
            reason = "away"
        else:
            continue
        groups[reason].append(pilot["character_name"])
    groups["not_in_fleet"] = list(shared.get("absent_volunteers") or [])
    return [
        {"reason": reason, "names": names}
        for reason, names in groups.items()
        if names
    ]


def _last_loss(shared, mine: set[int]):
    since = timezone.now() - RECENT_LOSS
    srp = set(shared["srp_killmails"])
    # A window cached before srp_covered_types existed offers SRP as before.
    covered = shared.get("srp_covered_types")
    for loss in shared["losses"]:  # newest first
        if datetime.fromisoformat(loss["killmail_time"]) < since:
            break
        if loss["victim_character_id"] in mine:
            return {
                **{
                    k: v for k, v in loss.items() if k != "victim_character_id"
                },
                "srp_filed": loss["killmail_id"] in srp,
                "srp_covered": covered is None
                or loss["ship_type_id"] in covered,
            }
    return None


def fleet_window(fleet, user, shared=None) -> dict:
    """The window payload for ``user`` (FleetWindowResponse)."""
    shared = shared or shared_fleet_window(fleet)
    mine = _character_ids(user)
    my_pilots = [p for p in shared["pilots"] if p["character_id"] in mine]

    if user.id == shared["fc_user_id"] or shared["boss_id"] in mine:
        mode = "fc"
    elif my_pilots and shared["fleet"]["live"]:
        mode = "member"
    else:
        mode = "viewer"
    is_fc = mode == "fc"

    return {
        "mode": mode,
        "fleet": shared["fleet"],
        "counts": shared["counts"],
        "ships": shared["ships"],
        "roles": shared["roles"],
        "needs": _needs(shared),
        "me": {
            "character_ids": sorted(mine),
            "characters": my_pilots if shared["fleet"]["live"] else [],
            "ship_volunteers": {
                character_id: key
                for character_id, key in shared["volunteers"].items()
                if character_id in mine
            },
            "last_loss": _last_loss(shared, mine),
        },
        # The roster is the FC's alone.
        "pilots": (
            shared["pilots"] if is_fc and shared["fleet"]["live"] else []
        ),
        "attention": (
            _attention(shared) if is_fc and shared["fleet"]["live"] else []
        ),
        "after_action": shared["after_action"] if is_fc else None,
        "feed": shared.get("feed", []) if is_fc else [],
        # Rounds for the FC and pilots in the fleet, as on the web.
        "fights": shared.get("fights") if mode in ("fc", "member") else None,
    }
