"""One endpoint: see the function below."""

from __future__ import annotations


from django.shortcuts import get_object_or_404

from app.errors import ErrorResponse
from authentication import AuthBearer

from campaigns.endpoints.base import router
from campaigns.endpoints.manage import _can_manage, _denied
from campaigns.models import (
    Campaign,
    CampaignStructure,
)


@router.delete(
    "/{slug}/structures/{structure_id}",
    response={200: dict, 403: ErrorResponse},
    auth=AuthBearer(),
)
def delete_structure(request, slug: str, structure_id: int):
    campaign = get_object_or_404(Campaign, slug=slug)
    if not _can_manage(request.user, campaign):
        return _denied()
    get_object_or_404(
        CampaignStructure, id=structure_id, campaign=campaign
    ).delete()
    return {"deleted": True}
