"""DELETE /corporations/{corporation_id}/discord/fleet-follows/{tribe_group_id}
- stop getting a tribe group's fleet posts in the corporation's Discord."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.endpoints.corporations.schemas import CorporationFleetFollows
from eveonline.helpers.corporations.fleet_follows import remove_follow
from eveonline.helpers.corporations.permissions import (
    can_edit_corporation_settings,
)
from eveonline.helpers.corporations.profile import load_corporation

PATH = "corporations/{corporation_id}/discord/fleet-follows/{tribe_group_id}"
METHOD = "delete"
ROUTE_SPEC = {
    "response": {
        200: CorporationFleetFollows,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": (
        "Stop a tribe group's fleet posts in this corporation's Discord "
        "(CEO and directors)"
    ),
}


def delete_corporation_fleet_follow(
    request, corporation_id: int, tribe_group_id: int
):
    corporation = load_corporation(corporation_id)
    if corporation is None:
        return 404, ErrorResponse(detail="Corporation not found")
    if not can_edit_corporation_settings(request.user, corporation):
        return 403, ErrorResponse(detail="Not authorised")
    return remove_follow(corporation, tribe_group_id)
