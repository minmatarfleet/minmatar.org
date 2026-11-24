"""Shared lookups for the fleet voice endpoints."""

from authentication import AuthBearer
from app.errors import ErrorResponse
from fleets.models import EveFleet
from groups.helpers.feature_access import can_use_feature
from voice.permissions import can_manage_voice

AUTH = AuthBearer()


def managed_fleet(request, fleet_id: int):
    """(fleet, None) when the user runs this fleet's voice, else (None, error)."""
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if fleet is None or not can_use_feature(
        request.user, "fleets.view", fleet=fleet
    ):
        return None, (404, ErrorResponse(detail="Fleet not found."))
    if not can_manage_voice(request.user, fleet):
        return None, (403, ErrorResponse(detail="Only the fleet's FC."))
    return fleet, None
