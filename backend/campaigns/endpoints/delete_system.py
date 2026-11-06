"""One endpoint: see the function below."""

from __future__ import annotations


from django.shortcuts import get_object_or_404
from django.utils import timezone

from app.errors import ErrorResponse
from authentication import AuthBearer

from campaigns.endpoints.base import router
from campaigns.endpoints.manage import _can_manage, _denied
from campaigns.models import (
    Campaign,
    CampaignSystem,
)


@router.delete(
    "/{slug}/systems/{system_id}",
    response={200: dict, 403: ErrorResponse},
    auth=AuthBearer(),
)
def retire_system(request, slug: str, system_id: int):
    """Retire, not delete: the history of kills and targets stays attached."""
    campaign = get_object_or_404(Campaign, slug=slug)
    if not _can_manage(request.user, campaign):
        return _denied()
    system = get_object_or_404(CampaignSystem, id=system_id, campaign=campaign)
    system.retired_at = timezone.now()
    system.save(update_fields=["retired_at"])
    return {"retired": True}
