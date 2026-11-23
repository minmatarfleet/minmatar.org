"""One endpoint: see the function below."""

from __future__ import annotations

from app.errors import ErrorResponse
from authentication import AuthBearer
from campaigns.endpoints import schemas
from campaigns.endpoints.base import router
from campaigns.endpoints.manage import _can_edit, _denied
from campaigns.endpoints.roles_helpers import _campaign
from campaigns.services import role_suggestions


@router.get(
    "/{slug}/roles/suggestions",
    response={
        200: schemas.CampaignRoleSuggestionsOut,
        403: ErrorResponse,
        404: None,
    },
    auth=AuthBearer(),
)
def get_role_suggestions(request, slug: str):
    """Everyone on the campaign's coordination server, each with the EVE
    character they most likely fly and the roles they already hold, for
    whoever may add role holders. A guess to invite from, cached for ten
    minutes; Sync now refreshes it."""
    campaign, _, denied = _campaign(request, slug)
    if denied:
        return denied
    if not _can_edit(request.user, campaign, "roles"):
        return _denied()
    return role_suggestions.suggestions(campaign)
