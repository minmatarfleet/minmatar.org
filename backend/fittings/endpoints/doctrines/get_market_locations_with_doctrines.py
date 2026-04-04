"""GET /market/locations - fittings from doctrines at market-active locations."""

from typing import List

from django.db.models import OuterRef, Subquery

from eveonline.models import EveLocation
from eveuniverse.models import EveType

from fittings.endpoints.doctrines.schemas import DoctrineFittingResponse
from fittings.models import EveDoctrineFitting

PATH = "market/locations"
METHOD = "get"
ROUTE_SPEC = {
    "description": (
        "Get all fittings from doctrines assigned to market-active locations"
    ),
    "response": {200: List[DoctrineFittingResponse]},
}


def get_market_locations_with_doctrines(
    request,
) -> List[DoctrineFittingResponse]:
    """
    Returns all fittings that belong to doctrines assigned to market-active locations.
    Fittings are sorted by ship volume (desc) then name. Excludes secondary fittings.
    """
    active_locations = EveLocation.objects.filter(market_active=True)

    ship_volume_subquery = EveType.objects.filter(
        id=OuterRef("fitting__ship_id")
    ).values("packaged_volume")[:1]

    doctrine_fittings = (
        EveDoctrineFitting.objects.filter(
            doctrine__locations__in=active_locations
        )
        .exclude(role="secondary")
        .select_related("fitting")
        .annotate(ship_volume=Subquery(ship_volume_subquery))
        .distinct()
        .order_by("-ship_volume", "fitting__name")
    )

    response = []
    seen_fitting_ids = set()

    for doctrine_fitting in doctrine_fittings:
        fitting = doctrine_fitting.fitting

        if fitting.id in seen_fitting_ids:
            continue

        seen_fitting_ids.add(fitting.id)

        response.append(
            DoctrineFittingResponse(
                fitting_id=fitting.id,
                fitting_name=fitting.name,
                role=doctrine_fitting.role,
            )
        )

    return response
