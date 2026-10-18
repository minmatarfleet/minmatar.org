"""
Who flew a fleet, read back from the tracked roster.

Every instance of the fleet counts, so a pilot who was in two instances is
still one pilot. Ship history comes from the append-only ship snapshots;
the member row holds the last ship the poller saw.

- What the fleet flew counts each pilot once, by the first hull they were
  in that is not a capsule (the member row when no snapshot has one).
- Roles flown look at every hull a pilot was in, so a pilot who reshipped
  into logi counts as logi. Hulls are matched to roles the same way a pilot
  in a live fleet is (``role_coverage.hull_roles``): the fleet's
  composition fit for that hull, else logi from a logi hull group. The fit
  a pilot actually flew is not known, so an off-doctrine links or cyno hull
  is not counted.
- No-shows are ship sign-ups whose character never joined any instance.
"""

from collections import Counter

from eveuniverse.models import EveType
from eveonline.killmail_classes import is_capsule
from fittings.models import EveFitting

from fleets.helpers.role_coverage import hull_roles

CAPSULE_NAME = "Capsule"

# (key, label, FitRoles predicate), in display order.
ROLES_FLOWN = (
    ("logi", "Logistics", lambda roles: roles.logi),
    ("links", "Links", lambda roles: roles.links),
    ("cyno", "Cyno", lambda roles: roles.cyno),
)


def _is_pod(ship_type_id, ship_name) -> bool:
    return is_capsule(ship_type_id) or ship_name == CAPSULE_NAME


def _pilot_ships(fleet) -> dict[int, dict]:
    """Per character: name, ship snapshots in order, member rows in order."""
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
    ) in members.values_list(
        "character_id", "character_name", "ship_type_id", "ship_name"
    ):
        pilot = pilots.setdefault(
            character_id, {"name": "", "snapshots": [], "members": []}
        )
        pilot["name"] = character_name
        pilot["members"].append((ship_type_id, ship_name))

    snapshots = EveFleetInstanceMemberShipSnapshot.objects.filter(
        member__eve_fleet_instance__eve_fleet=fleet
    ).order_by("created_at", "id")
    for character_id, ship_type_id, ship_name in snapshots.values_list(
        "member__character_id", "ship_type_id", "ship_name"
    ):
        pilots[character_id]["snapshots"].append((ship_type_id, ship_name))
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


def _roles_flown(fleet, pilots, visible) -> list[dict]:
    flown = {
        character_id: _hulls_flown(pilot)
        for character_id, pilot in pilots.items()
    }
    roles_by_hull = hull_roles(
        fleet, {type_id for hulls in flown.values() for type_id, _ in hulls}
    )
    rows = []
    for key, label, fills in ROLES_FLOWN:
        flyers = []
        for character_id, hulls in flown.items():
            # The pilot's first hull that fills the role stands for them.
            hull = next((h for h in hulls if fills(roles_by_hull[h[0]])), None)
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


def fleet_no_shows(fleet, member_ids: set[int]) -> dict:
    """Ship sign-ups whose character never joined the fleet."""
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
        "joined_without_signing_up": len(member_ids - volunteer_ids),
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


def fleet_participants(fleet, visible=lambda character_id: True) -> dict:
    """
    Hulls flown, reships, pods and roles flown for a fleet's tracked pilots.

    ``visible`` limits which pilots are named in roles flown; the counts
    cover everyone.
    """
    pilots = _pilot_ships(fleet)

    first_ships = Counter()
    first_names = {}
    for pilot in pilots.values():
        type_id, name = _first_ship(pilot)
        first_ships[type_id] += 1
        first_names.setdefault(type_id, name)

    return {
        "pilots": len(pilots),
        "flew": sorted(
            (
                {
                    "ship_type_id": type_id,
                    "ship_name": first_names[type_id],
                    "count": count,
                }
                for type_id, count in first_ships.items()
            ),
            key=lambda row: (-row["count"], row["ship_name"]),
        ),
        "changed_ship": sum(
            1
            for pilot in pilots.values()
            if len({type_id for type_id, _ in pilot["snapshots"]}) > 1
        ),
        "ended_in_pod": sum(
            1 for pilot in pilots.values() if _is_pod(*pilot["members"][-1])
        ),
        "roles_flown": _roles_flown(fleet, pilots, visible),
        "member_ids": set(pilots),
    }
