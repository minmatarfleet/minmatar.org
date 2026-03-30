"""GET /v2 — deprecated list of fleet id + audience."""

import logging
from datetime import timedelta
from typing import List

from django.utils import timezone

from fleets.endpoints.schemas import EveFleetListResponse
from fleets.models import EveFleet

logger = logging.getLogger(__name__)

PATH = "/v2"
METHOD = "get"
ROUTE_SPEC = {
    "deprecated": True,
    "response": {200: List[EveFleetListResponse]},
}


def get_v2_fleets(request, upcoming: bool = True, active: bool = False):
    logger.warning(
        "Deprecated /fleets/v2 endpoint called by user %s", request.user
    )
    if active:
        fleets = (
            EveFleet.objects.filter(evefleetinstance__end_time=None)
            .filter(start_time__gte=timezone.now() - timedelta(hours=1))
            .order_by("-start_time")
        )
    elif upcoming:
        fleets = EveFleet.objects.filter(
            start_time__gte=timezone.now()
        ).order_by("-start_time")
    else:
        fleets = EveFleet.objects.filter(
            start_time__gte=timezone.now() - timedelta(days=30)
        ).order_by("-start_time")
    response = []
    for fleet in fleets:
        response.append(
            {
                "id": fleet.id,
                "audience": fleet.audience.name,
            }
        )
    return response
