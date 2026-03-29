"""POST /{fleet_id}/preping — send Discord pre-ping for a scheduled fleet."""

import logging

from app.errors import ErrorResponse
from authentication import AuthBearer

from fleets.endpoints.helpers import send_discord_pre_ping
from fleets.models import EveFleet

logger = logging.getLogger(__name__)

PATH = "/{fleet_id}/preping"
METHOD = "post"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        202: str,
        403: ErrorResponse,
        404: ErrorResponse,
        500: ErrorResponse,
    },
    "description": "Send a Discord pre-ping for a fleet. No request body needed.",
}


def send_pre_ping(request, fleet_id):
    fleet = EveFleet.objects.filter(id=fleet_id).first()

    if not fleet:
        return 404, ErrorResponse(detail="Fleet not found")

    if request.user != fleet.created_by:
        return 403, {
            "detail": "User does not have permission to delete this fleet"
        }

    sent = send_discord_pre_ping(fleet)

    if sent:
        return 202, "Sent"
    else:
        return 500, ErrorResponse.log(
            "Error sending pre-ping", f"Unable to pre-ping fleet {fleet.id}"
        )
