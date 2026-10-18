"""
Hulls a fleet report must not reveal to everyone.

Who brought capitals, jump freighters, cynos and covert hulls tells an enemy
what the alliance can drop and from where. Reports that list pilots or hulls
(the Participants tab) remove every pilot who flew one of these for viewers
who are not Strategic FCs.

A hull is sensitive when its EVE group is a capital, jump freighter, capital
industrial (Rorqual), force recon or black ops group, or when the fleet's
fit for it is a cyno fit (``role_coverage.hull_roles``).
"""

from collections.abc import Iterable, Mapping

from eveuniverse.models import EveType

from feed.constants import CAPITAL_SHIP_GROUPS
from fleets.helpers.fit_roles import FitRoles
from fleets.helpers.role_coverage import hull_roles

SENSITIVE_HULL_GROUPS = CAPITAL_SHIP_GROUPS | frozenset(
    {
        "Lancer Dreadnought",
        "Jump Freighter",
        "Capital Industrial Ship",
        "Force Recon Ship",
        "Black Ops",
    }
)


def sensitive_hull_ids(
    fleet,
    ship_type_ids: Iterable[int],
    roles_by_hull: Mapping[int, FitRoles] | None = None,
) -> set[int]:
    """The hulls in ``ship_type_ids`` that are sensitive for this fleet.

    Pass ``roles_by_hull`` when the caller already has ``hull_roles`` for
    these hulls, to save the composition lookup.
    """
    ship_type_ids = set(ship_type_ids)
    if not ship_type_ids:
        return set()
    if roles_by_hull is None:
        roles_by_hull = hull_roles(fleet, ship_type_ids)
    sensitive = set(
        EveType.objects.filter(
            id__in=ship_type_ids, eve_group__name__in=SENSITIVE_HULL_GROUPS
        ).values_list("id", flat=True)
    )
    sensitive.update(
        type_id
        for type_id in ship_type_ids
        if type_id in roles_by_hull and roles_by_hull[type_id].cyno
    )
    return sensitive


def sensitive_pilot_ids(
    hulls_by_pilot: Mapping[int, Iterable[int]], sensitive: set[int]
) -> set[int]:
    """Pilots who flew any sensitive hull."""
    return {
        character_id
        for character_id, hulls in hulls_by_pilot.items()
        if sensitive.intersection(hulls)
    }
