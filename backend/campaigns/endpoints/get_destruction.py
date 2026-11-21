"""One endpoint: see the function below."""

from __future__ import annotations

from app.errors import ErrorResponse
from authentication import AuthOptional

from campaigns.endpoints import schemas
from campaigns.endpoints.base import router
from campaigns.endpoints.public import _clamp, _get, _may_read
from campaigns.services import destruction as destruction_service


@router.get(
    "/{slug}/destruction",
    response={
        200: schemas.CampaignDestructionOut,
        403: ErrorResponse,
        404: None,
    },
    auth=AuthOptional(),
)
def get_campaign_destruction(request, slug: str, limit: int = 50):
    """The Destruction tab: this week's ISK, structures killed, the biggest
    kill, and the kills themselves, newest first."""
    campaign = _get(request, slug)
    denied = _may_read(request, campaign)
    if denied:
        return denied
    return destruction_service.destruction(campaign, limit=_clamp(limit))
