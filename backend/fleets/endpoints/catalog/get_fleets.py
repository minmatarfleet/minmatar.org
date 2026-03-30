"""GET \"\" — list fleet IDs (upcoming, active, or recent)."""

from datetime import timedelta
from typing import List

from django.utils import timezone

from fleets.models import EveFleet

PATH = ""
METHOD = "get"
ROUTE_SPEC = {
    "response": {200: List[int]},
}


def get_fleets(request, upcoming: bool = True, active: bool = False):
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
    return [fleet.id for fleet in fleets]
