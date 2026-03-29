"""GET /{fleet_id}/users — user IDs in the fleet audience groups."""

from typing import List

from authentication import AuthBearer

from fleets.endpoints.schemas import EveFleetUsersResponse
from fleets.models import EveFleet

PATH = "/{fleet_id}/users"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: List[EveFleetUsersResponse], 403: None, 404: None},
    "description": "Get user IDs in the fleet audience groups. Requires fleets.view_evefleet.",
}


def get_fleet_users(request, fleet_id: int):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, None
    if not request.user.has_perm("fleets.view_evefleet"):
        return 403, None

    audience = fleet.audience
    groups = audience.groups.all()

    users = set()
    for group in groups:
        for user in group.user_set.all():
            users.add(user.id)

    return [{"fleet_id": fleet_id, "user_ids": list(users)}]
