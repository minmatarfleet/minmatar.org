"""GET /training/hulls - your best character and doctrine fit on each hull, for the Fleet Roles guide ladders."""

from authentication import AuthBearer
from capabilities import training
from capabilities.endpoints.schemas import HullReadinessResponse

PATH = "/hulls"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Your best character and doctrine fit on each hull, for the Fleet Roles guide ladders",
    "auth": AuthBearer(),
    "response": {200: list[HullReadinessResponse]},
}


def get_hulls(request, type_ids: str):
    """type_ids: comma-separated ship type ids, at most twelve."""
    ids = []
    for part in type_ids.split(","):
        part = part.strip()
        if part.isdigit():
            ids.append(int(part))
    return 200, training.hull_readiness(request.user, ids)
