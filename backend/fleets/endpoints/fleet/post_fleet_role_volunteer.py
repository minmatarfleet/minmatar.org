"""POST /{fleet_id}/role-volunteers — sign up a character for a role."""

import logging

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.helpers.characters import user_characters

from fleets.endpoints.helpers import _fleet_authorized
from fleets.endpoints.schemas import (
    CreateEveFleetRoleVolunteerRequest,
    EveFleetRoleVolunteerResponse,
)
from fleets.models import EveFleet, EveFleetInstance, EveFleetRoleVolunteer

logger = logging.getLogger(__name__)

PATH = "/{fleet_id}/role-volunteers"
METHOD = "post"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: EveFleetRoleVolunteerResponse,
        403: None,
        404: None,
        400: ErrorResponse,
    },
    "description": "Volunteer a character for a fleet role. Character must belong to the user.",
}


def create_fleet_role_volunteer(
    request, fleet_id: int, payload: CreateEveFleetRoleVolunteerRequest
):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, None
    if not _fleet_authorized(request, fleet):
        return 403, None
    allowed_ids = {
        c.character_id: c.character_name for c in user_characters(request.user)
    }
    if payload.character_id not in allowed_ids:
        return 400, {
            "detail": "Character not found or not one of your characters"
        }
    valid_roles = [c[0] for c in EveFleetRoleVolunteer.ROLE_CHOICES]
    if payload.role not in valid_roles:
        return 400, {"detail": f"Invalid role. Must be one of: {valid_roles}"}
    if payload.subtype is not None and payload.subtype != "":
        valid_subtypes = [c[0] for c in EveFleetRoleVolunteer.SUBTYPE_CHOICES]
        if payload.subtype not in valid_subtypes:
            return 400, {
                "detail": f"Invalid subtype. Must be one of: {valid_subtypes}"
            }
    volunteer, _ = EveFleetRoleVolunteer.objects.update_or_create(
        eve_fleet=fleet,
        character_id=payload.character_id,
        role=payload.role,
        defaults={
            "character_name": allowed_ids[payload.character_id],
            "subtype": payload.subtype or None,
            "quantity": payload.quantity,
        },
    )
    instance = EveFleetInstance.objects.filter(
        eve_fleet=fleet, end_time__isnull=True
    ).first()
    if instance:
        try:
            instance.refresh_motd()
        except Exception as e:
            logger.warning(
                "Failed to refresh MOTD for fleet %s: %s", fleet_id, e
            )
    return 200, EveFleetRoleVolunteerResponse(
        id=volunteer.id,
        character_id=volunteer.character_id,
        character_name=volunteer.character_name,
        role=volunteer.role,
        subtype=volunteer.subtype,
        quantity=volunteer.quantity,
    )
