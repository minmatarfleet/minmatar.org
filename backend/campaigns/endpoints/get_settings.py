"""One endpoint: see the function below."""

from __future__ import annotations


from django.shortcuts import get_object_or_404

from app.errors import ErrorResponse
from authentication import AuthBearer

from campaigns.endpoints import schemas
from campaigns.endpoints.base import router
from campaigns.endpoints.manage import _can_manage, _denied
from campaigns.endpoints.settings_helpers import _settings
from campaigns.models import (
    Campaign,
)


@router.get(
    "/{slug}/settings",
    response={200: schemas.CampaignSettingsOut, 403: ErrorResponse},
    auth=AuthBearer(),
)
def get_settings(request, slug: str):
    """Everything an operator edits on one campaign, in one read."""
    campaign = get_object_or_404(Campaign, slug=slug)
    if not _can_manage(request.user, campaign):
        return _denied()
    return _settings(campaign)
