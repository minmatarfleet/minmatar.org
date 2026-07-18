"""Map sell-order items to doctrine ships that drive their expectations."""

from __future__ import annotations

from collections import defaultdict

from market.models import EveMarketContractExpectation
from market.models.item import (
    EveMarketFittingExpectation,
    _get_consumable_items,
)


def item_ships_by_location(locations) -> dict[int, dict[str, list[dict]]]:
    """
    Map location_pk -> item_name -> [{ship_id, fitting_name}] for doctrine
    ships that drive sell-order expectations for that item.
    """
    location_pks = [location.pk for location in locations]
    # item_name -> ship_id -> fitting_name (one entry per hull)
    by_location: dict[int, dict[str, dict[int, str]]] = {
        pk: defaultdict(dict) for pk in location_pks
    }

    def add(location_pk: int, item_name: str, fitting) -> None:
        ships = by_location[location_pk][item_name]
        if fitting.ship_id not in ships:
            ships[fitting.ship_id] = fitting.name

    for fexp in EveMarketFittingExpectation.objects.filter(
        location_id__in=location_pks
    ).select_related("fitting"):
        for item_name in fexp.get_item_quantities():
            add(fexp.location_id, item_name, fexp.fitting)

    for cexp in EveMarketContractExpectation.objects.filter(
        location_id__in=location_pks
    ).select_related("fitting"):
        for item_name in _get_consumable_items(cexp.fitting):
            add(cexp.location_id, item_name, cexp.fitting)

    return {
        location_pk: {
            item_name: [
                {"ship_id": ship_id, "fitting_name": fitting_name}
                for ship_id, fitting_name in sorted(
                    ships.items(), key=lambda row: row[1].lower()
                )
            ]
            for item_name, ships in by_item.items()
        }
        for location_pk, by_item in by_location.items()
    }
