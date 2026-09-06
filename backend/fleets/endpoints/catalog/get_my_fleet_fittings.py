"""GET /my-fittings — manual EFT fits this FC has used on their fleets before."""

from typing import List

from authentication import AuthBearer
from eveuniverse.models import EveType

from fleets.endpoints.schemas import MyFleetFittingResponse
from fleets.models import EveFleetFitting

PATH = "/my-fittings"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: List[MyFleetFittingResponse]},
    "description": (
        "Custom (pasted EFT) fits the caller has added to fleets they "
        "created, most recently used first, one entry per fit name and hull."
    ),
}


def get_my_fleet_fittings(request):
    rows = (
        EveFleetFitting.objects.filter(
            eve_fleet__created_by=request.user, fitting__isnull=True
        )
        .exclude(eft_format="")
        .order_by("-created_at", "-id")
        .values("name", "ship_id", "eft_format")
    )
    seen: set[tuple[str, int]] = set()
    unique = []
    for row in rows:
        key = (row["name"].lower(), row["ship_id"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    ship_names = dict(
        EveType.objects.filter(
            id__in={row["ship_id"] for row in unique}
        ).values_list("id", "name")
    )
    return [
        MyFleetFittingResponse(
            name=row["name"],
            ship_id=row["ship_id"],
            ship_name=ship_names.get(row["ship_id"], ""),
            eft_format=row["eft_format"],
        )
        for row in unique[:50]
    ]
