"""Ship targets beyond the line list itself: lines to start from, ships on
no line, who could fill a short line and what a pilot's hangar can bring.

The line list, progress and saving live in fleets.helpers.private_fleets.
See docs/fleets/private-fleets.md.
"""

from __future__ import annotations

from collections import defaultdict

from eveonline.constants import MINMATAR_FLEET_ALLIANCE_ID
from eveonline.models import EveCharacterAsset
from fleets.helpers.composition import fleet_composition
from fleets.helpers.private_fleets import (
    _group_ids_by_type,
    _line_matches,
    volunteer_hulls,
)
from fleets.models import EveFleet, EveFleetInvite, EveFleetShipTarget

# Find pilots lists at most this many players for one line.
MAX_LINE_OWNERS = 50
# Copy from lists the creator's last few fleets that had targets.
MAX_PAST_FLEETS = 5


def doctrine_target_lines(fleet: EveFleet) -> list[dict]:
    """One line per EVE group in the fleet's composition, in role order,
    listing the composition's hulls in that group. The FC types the counts."""
    lines: dict[str, list[int]] = {}
    for entry in fleet_composition(fleet):
        if not entry.ship_id:
            continue
        name = entry.ship_group or entry.ship_name or entry.name
        hulls = lines.setdefault(name, [])
        if entry.ship_id not in hulls:
            hulls.append(entry.ship_id)
    return [
        {"name": name[:64], "ship_type_ids": hulls}
        for name, hulls in lines.items()
    ]


def past_target_fleets(user, exclude_fleet_id: int) -> list[dict]:
    """The user's own recent fleets that had targets, to copy lines from.
    Only fleets they created, so a private fleet never leaks to someone
    else."""
    fleets = (
        EveFleet.objects.filter(created_by=user, ship_targets__isnull=False)
        .exclude(id=exclude_fleet_id)
        .distinct()
        .order_by("-start_time")[:MAX_PAST_FLEETS]
    )
    out = []
    for fleet in fleets:
        out.append(
            {
                "fleet_id": fleet.id,
                "title": fleet.objective or fleet.description or "Fleet",
                "start_time": fleet.start_time,
                "lines": [
                    {
                        "name": target.name,
                        "target": target.target,
                        "ship_type_ids": list(target.ship_type_ids or []),
                        "group_ids": list(target.group_ids or []),
                    }
                    for target in fleet.ship_targets.all()
                ],
            }
        )
    return out


def unmatched_hulls(fleet: EveFleet) -> list[dict]:
    """Hulls signed up that no target line counts, with how many
    characters fly each. Empty when the fleet has no targets."""
    targets = list(EveFleetShipTarget.objects.filter(eve_fleet=fleet))
    if not targets:
        return []
    hulls = volunteer_hulls(fleet)
    groups = _group_ids_by_type({type_id for _, type_id in hulls})
    characters: dict[int, set[int]] = defaultdict(set)
    for character_id, type_id in hulls:
        if not any(
            _line_matches(target, type_id, groups.get(type_id))
            for target in targets
        ):
            characters[type_id].add(character_id)
    names = _type_names(characters.keys())
    return [
        {
            "ship_type_id": type_id,
            "ship_name": names.get(type_id, f"Ship {type_id}"),
            "characters": len(ids),
        }
        for type_id, ids in sorted(
            characters.items(), key=lambda item: (-len(item[1]), item[0])
        )
    ]


def line_owners(fleet: EveFleet, target: EveFleetShipTarget) -> list[dict]:
    """Alliance players not yet invited who own a hull this line counts,
    from their characters' ESI assets. One row per player: the first
    matching hull found, at the fleet's form-up location when they have
    one there."""
    invited = set(
        EveFleetInvite.objects.filter(eve_fleet=fleet).values_list(
            "user_id", flat=True
        )
    )
    if fleet.created_by_id:
        invited.add(fleet.created_by_id)
    type_ids = line_type_ids(target)
    if not type_ids:
        return []
    assets = list(
        EveCharacterAsset.objects.filter(
            type_id__in=type_ids,
            character__alliance_id=MINMATAR_FLEET_ALLIANCE_ID,
            character__user__is_active=True,
        )
        .exclude(character__user_id__in=invited)
        .values_list(
            "character__user_id",
            "character__character_id",
            "character__character_name",
            "type_id",
            "type_name",
            "location_name",
        )
        .order_by("character__user_id", "id")
    )
    formup = _formup_name(fleet)
    best: dict[int, dict] = {}
    for user_id, character_id, name, type_id, type_name, location in assets:
        here = bool(formup) and formup in (location or "")
        current = best.get(user_id)
        if current and (current["at_formup"] or not here):
            continue
        best[user_id] = {
            "user_id": user_id,
            "character_id": character_id,
            "character_name": name,
            "ship_type_id": type_id,
            "ship_name": type_name,
            "location_name": location or "",
            "at_formup": here,
        }
    rows = sorted(
        best.values(),
        key=lambda row: (
            not row["at_formup"],
            row["location_name"],
            row["character_name"],
        ),
    )
    return rows[:MAX_LINE_OWNERS]


def my_target_hangar(fleet: EveFleet, user) -> dict:
    """For the ship picker: which target line each composition hull counts
    toward, and which composition hulls each of the user's characters
    owns (from ESI assets)."""
    composition_hulls = {
        entry.ship_id for entry in fleet_composition(fleet) if entry.ship_id
    }
    targets = list(EveFleetShipTarget.objects.filter(eve_fleet=fleet))
    groups = _group_ids_by_type(composition_hulls)
    lines = []
    for type_id in sorted(composition_hulls):
        for target in targets:
            if _line_matches(target, type_id, groups.get(type_id)):
                lines.append({"ship_type_id": type_id, "target_id": target.id})
                break
    owned: dict[int, set[int]] = defaultdict(set)
    if composition_hulls:
        for character_id, type_id in EveCharacterAsset.objects.filter(
            character__user=user, type_id__in=composition_hulls
        ).values_list("character__character_id", "type_id"):
            owned[character_id].add(type_id)
    return {
        "lines_by_ship": lines,
        "hangars": [
            {"character_id": character_id, "ship_type_ids": sorted(types)}
            for character_id, types in sorted(owned.items())
        ],
    }


def line_type_ids(target: EveFleetShipTarget) -> set[int]:
    """Every hull a line counts: its hulls plus each hull in its groups."""
    # pylint: disable=import-outside-toplevel
    from eveuniverse.models import EveType

    type_ids = set(target.ship_type_ids or [])
    if target.group_ids:
        type_ids |= set(
            EveType.objects.filter(
                eve_group_id__in=list(target.group_ids)
            ).values_list("id", flat=True)
        )
    return type_ids


def _type_names(type_ids) -> dict[int, str]:
    # pylint: disable=import-outside-toplevel
    from eveuniverse.models import EveType

    return dict(
        EveType.objects.filter(id__in=list(type_ids)).values_list("id", "name")
    )


def _formup_name(fleet: EveFleet) -> str:
    location = fleet.formup_location or fleet.location
    if not location:
        return ""
    return location.solar_system_name or location.location_name or ""
