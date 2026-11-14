"""GET /training/roles - who flies a role most this year, and recent fleets that flew it, for the Fleet Roles guides."""

from authentication import AuthBearer
from capabilities.endpoints.schemas import RoleSpotlightResponse
from capabilities.role_spotlight import role_spotlight

PATH = "/roles"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Who flies a role most this year, and recent fleets that flew it",
    "auth": AuthBearer(),
    "response": {200: RoleSpotlightResponse},
}


def get_roles(request, capabilities: str, type_ids: str):
    """capabilities: comma-separated classes; type_ids: the ladder hulls."""
    names = [c.strip() for c in capabilities.split(",") if c.strip()]
    ids = [int(p) for p in type_ids.split(",") if p.strip().isdigit()]
    return 200, role_spotlight(names, ids)
