"""One endpoint: see the function below."""

from __future__ import annotations

from app.errors import ErrorResponse
from authentication import AuthBearer
from campaigns.endpoints import schemas
from campaigns.endpoints.base import router
from campaigns.endpoints.coordinator_helpers import _managed
from campaigns.endpoints.settings_helpers import coordinators_out
from campaigns.services import coordinators as coordinator_service


@router.post(
    "/{slug}/coordinators",
    response={
        200: list[schemas.CampaignCoordinatorOut],
        400: ErrorResponse,
        403: ErrorResponse,
        404: None,
    },
    auth=AuthBearer(),
)
def invite_coordinator(
    request, slug: str, payload: schemas.CampaignCoordinatorInvite
):
    """Invite a character from outside the alliance to help run the
    campaign, by exact character name."""
    campaign, denied = _managed(request, slug)
    if denied:
        return denied
    try:
        coordinator_service.invite(
            campaign, payload.character_name, request.user
        )
    except coordinator_service.NotFound:
        return 400, {"detail": "No character has that exact name."}
    return coordinators_out(campaign)
