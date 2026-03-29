"""POST /start-now — quick-start fleet from current in-game fleet."""

import logging
from typing import Optional

from app.errors import ErrorResponse
from authentication import AuthBearer
from django.utils import timezone
from eveonline.helpers.characters import user_characters

from fleets.endpoints.helpers import make_fleet_response
from fleets.endpoints.schemas import EveFleetResponse, StartFleetNowRequest
from fleets.models import EveFleet, EveFleetAudience

logger = logging.getLogger(__name__)

PATH = "/start-now"
METHOD = "post"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: EveFleetResponse,
        403: ErrorResponse,
        400: ErrorResponse,
    },
    "description": "Create a fleet with defaults, link to your current in-game fleet, and activate (no Discord). Must be in a fleet and have fleets.add_evefleet.",
}


def start_fleet_now(request, payload: Optional[StartFleetNowRequest] = None):
    if not request.user.has_perm("fleets.add_evefleet"):
        return 403, {"detail": "User missing permission fleets.add_evefleet"}

    audience = EveFleetAudience.objects.filter(hidden=False).first()
    if not audience:
        return 400, {"detail": "No fleet audience configured"}

    location = audience.staging_location

    quick_objective = (payload.objective or "").strip() if payload else ""
    fleet = EveFleet.objects.create(
        type="non_strategic",
        description="Quick start fleet",
        objective=quick_objective,
        start_time=timezone.now(),
        created_by=request.user,
        location=location,
        audience=audience,
        disable_motd=False,
        status="pending",
    )

    fc_character_id = payload.fc_character_id if payload else None
    if fc_character_id is not None:
        allowed_ids = [c.character_id for c in user_characters(request.user)]
        if fc_character_id not in allowed_ids:
            fleet.delete()
            return 400, {
                "detail": "Character not found or not one of your characters"
            }

    try:
        fleet.generate_esi_fleet(fc_character_id)
        fleet.activate()
    except Exception as e:
        fleet.delete()
        if "not in a fleet" in str(e):
            return 400, {"detail": "Not currently in a fleet"}
        logger.exception(
            "Quick start fleet failed for user %s", request.user.username
        )
        return 400, {"detail": str(e)}

    logger.info(
        "Fleet %d started (quick) by %s", fleet.id, request.user.username
    )
    return 200, make_fleet_response(fleet)
