"""One endpoint: see the function below."""

from __future__ import annotations

from app.errors import ErrorResponse
from authentication import AuthOptional

from campaigns.endpoints import schemas
from campaigns.endpoints.base import router
from campaigns.endpoints.public import _get, _may_read
from campaigns.services import timers


@router.get(
    "/{slug}/timers",
    response={
        200: list[schemas.CampaignTimerOut],
        403: ErrorResponse,
        404: None,
    },
    auth=AuthOptional(),
)
def get_campaign_timers(request, slug: str):
    """The campaign timerboard: upcoming soonest first, then done."""
    campaign = _get(request, slug)
    denied = _may_read(request, campaign)
    if denied:
        return denied
    return timers.campaign_timers(campaign)
