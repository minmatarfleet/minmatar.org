"""GET /v3 — full fleet cards (requires fleets.view_evefleet)."""

from datetime import timedelta
from typing import List, Union

from django.db.models import Q
from django.utils import timezone

from app.errors import ErrorResponse
from authentication import AuthBearer

from fleets.endpoints.helpers import make_fleet_response
from fleets.endpoints.schemas import EveFleetFilter, EveFleetResponse
from fleets.models import EveFleet

PATH = "/v3"
METHOD = "get"
ROUTE_SPEC = {
    "response": {
        200: List[EveFleetResponse],
        401: ErrorResponse,
        403: ErrorResponse,
    },
    "auth": AuthBearer(),
    "description": "List fleets matching the filter. Requires fleets.view_evefleet.",
}


def get_v3_fleets(
    request, fleet_filter: EveFleetFilter = EveFleetFilter.RECENT
) -> Union[List[EveFleetResponse], tuple[int, dict]]:
    if not request.user.has_perm("fleets.view_evefleet"):
        return 403, {"detail": "User missing permission fleets.view_evefleet"}

    if fleet_filter == EveFleetFilter.ACTIVE:
        fleets = (
            EveFleet.objects.filter(evefleetinstance__end_time=None)
            .filter(
                Q(
                    status__in=["cancelled", "pending"],
                    start_time__gte=timezone.now() - timedelta(hours=1),
                )
                | Q(
                    ~Q(status__in=["cancelled", "pending"]),
                    start_time__gte=timezone.now() - timedelta(hours=24),
                )
            )
            .order_by("-start_time")
        )
    elif fleet_filter == EveFleetFilter.UPCOMING:
        fleets = EveFleet.objects.filter(
            start_time__gte=timezone.now()
        ).order_by("-start_time")
    else:
        fleets = EveFleet.objects.filter(
            start_time__gte=timezone.now() - timedelta(days=30)
        ).order_by("-start_time")

    fleets = fleets.filter(audience__hidden=False)
    return [make_fleet_response(fleet) for fleet in fleets]
