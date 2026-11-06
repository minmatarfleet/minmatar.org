"""One endpoint: see the function below."""

from __future__ import annotations


from django.shortcuts import get_object_or_404

from app.errors import ErrorResponse
from authentication import AuthBearer

from campaigns.endpoints.base import router
from campaigns.endpoints.manage import _can_manage, _denied
from campaigns.models import (
    Campaign,
    CampaignFitting,
)


@router.delete(
    "/{slug}/fittings/{row_id}",
    response={200: dict, 403: ErrorResponse},
    auth=AuthBearer(),
)
def delete_fitting(request, slug: str, row_id: int):
    campaign = get_object_or_404(Campaign, slug=slug)
    if not _can_manage(request.user, campaign):
        return _denied()
    get_object_or_404(CampaignFitting, id=row_id, campaign=campaign).delete()
    return {"deleted": True}
