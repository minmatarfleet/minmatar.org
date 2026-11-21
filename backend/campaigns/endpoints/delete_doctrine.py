"""One endpoint: see the function below."""

from __future__ import annotations

from django.shortcuts import get_object_or_404

from app.errors import ErrorResponse
from authentication import AuthBearer
from campaigns.endpoints import schemas
from campaigns.endpoints.base import router
from campaigns.endpoints.coordinator_helpers import _doctrines_out, _managed
from campaigns.models import CampaignDoctrine


@router.delete(
    "/{slug}/doctrines/{campaign_doctrine_id}",
    response={
        200: schemas.CampaignDoctrinesOut,
        403: ErrorResponse,
        404: None,
    },
    auth=AuthBearer(),
)
def detach_doctrine(request, slug: str, campaign_doctrine_id: int):
    """Detach a doctrine and the fittings it brought in."""
    campaign, denied = _managed(request, slug)
    if denied:
        return denied
    get_object_or_404(
        CampaignDoctrine, campaign=campaign, id=campaign_doctrine_id
    ).delete()
    return _doctrines_out(campaign)
