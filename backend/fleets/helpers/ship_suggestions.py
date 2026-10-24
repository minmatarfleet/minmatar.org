"""
A starting ship for each character in the "What are you bringing?" picker.

Read from the hulls a character actually flew in tracked fleets (the member
row plus every ship snapshot, capsules left out) over the last 180 days. A
hull counts once per fleet. Only hulls in this fleet's composition can be
suggested; fleets on the same doctrine count first, then any fleet, then the
most recent. When the composition has several fits on that hull, the one the
character last volunteered for wins, else the first in composition order.

Nothing is saved: the picker pre-selects the ship and the pilot still
presses Save.
"""

from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from eveonline.killmail_classes import CAPSULE_TYPE_IDS

HISTORY_DAYS = 180


@dataclass
class ShipSuggestion:
    fitting_id: int | None
    fleet_fitting_id: int | None
    ship_name: str
    fleets: int  # past fleets the character flew this hull in


def suggest_ships(
    eve_fleet, character_ids: list[int], composition: list
) -> dict[int, ShipSuggestion]:
    """``{character_id: ShipSuggestion}`` for characters with a match."""
    # Imported here: fleets.models imports fleets.helpers modules.
    from fleets.models import (  # pylint: disable=import-outside-toplevel
        EveFleetInstanceMember,
        EveFleetInstanceMemberShipSnapshot,
        EveFleetShipVolunteer,
    )

    entries_by_hull: dict[int, list] = {}
    for entry in composition:
        entries_by_hull.setdefault(entry.ship_id, []).append(entry)
    if not entries_by_hull or not character_ids:
        return {}

    since = timezone.now() - timedelta(days=HISTORY_DAYS)
    members = list(
        EveFleetInstanceMember.objects.filter(
            character_id__in=character_ids, join_time__gte=since
        )
        .exclude(eve_fleet_instance__eve_fleet_id=eve_fleet.id)
        .values_list(
            "id",
            "character_id",
            "ship_type_id",
            "join_time",
            "eve_fleet_instance__eve_fleet_id",
            "eve_fleet_instance__eve_fleet__doctrine_id",
        )
    )
    hulls_by_member: dict[int, set[int]] = {
        member_id: {ship_type_id} for member_id, _, ship_type_id, *_ in members
    }
    for (
        member_id,
        ship_type_id,
    ) in EveFleetInstanceMemberShipSnapshot.objects.filter(
        member_id__in=hulls_by_member
    ).values_list(
        "member_id", "ship_type_id"
    ):
        hulls_by_member[member_id].add(ship_type_id)

    # (character_id, hull) -> {fleet_id: (same_doctrine, join_time)}
    flown: dict[tuple[int, int], dict[int, tuple[bool, object]]] = {}
    for (
        member_id,
        character_id,
        _,
        join_time,
        fleet_id,
        doctrine_id,
    ) in members:
        same_doctrine = bool(
            eve_fleet.doctrine_id and doctrine_id == eve_fleet.doctrine_id
        )
        for hull in hulls_by_member[member_id]:
            if hull in CAPSULE_TYPE_IDS or hull not in entries_by_hull:
                continue
            fleets = flown.setdefault((character_id, hull), {})
            seen = fleets.get(fleet_id)
            if not seen or join_time > seen[1]:
                fleets[fleet_id] = (same_doctrine, join_time)

    best: dict[int, tuple] = {}
    for (character_id, hull), fleets in flown.items():
        rank = (
            sum(1 for same, _ in fleets.values() if same),
            len(fleets),
            max(join_time for _, join_time in fleets.values()),
        )
        if character_id not in best or rank > best[character_id][0]:
            best[character_id] = (rank, hull, len(fleets))

    # Past fleets' fleet fittings are their own; only catalog fits carry over.
    last_picks: dict[int, list[int]] = {}
    for character_id, fitting_id in (
        EveFleetShipVolunteer.objects.filter(
            character_id__in=list(best),
            fitting_id__isnull=False,
            eve_fleet__start_time__gte=since,
        )
        .exclude(eve_fleet_id=eve_fleet.id)
        .order_by("-eve_fleet__start_time", "-id")
        .values_list("character_id", "fitting_id")
    ):
        last_picks.setdefault(character_id, []).append(fitting_id)

    suggestions = {}
    for character_id, (_, hull, fleet_count) in best.items():
        entry = _pick_entry(
            entries_by_hull[hull], last_picks.get(character_id, [])
        )
        suggestions[character_id] = ShipSuggestion(
            fitting_id=entry.fitting_id,
            fleet_fitting_id=(
                None if entry.fitting_id else entry.fleet_fitting_id
            ),
            ship_name=entry.ship_name,
            fleets=fleet_count,
        )
    return suggestions


def _pick_entry(entries: list, picks: list[int]):
    """The catalog fit last volunteered for on this hull, else the first."""
    for fitting_id in picks:
        for entry in entries:
            if entry.fitting_id == fitting_id:
                return entry
    return entries[0]
