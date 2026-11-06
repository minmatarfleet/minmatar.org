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
    CampaignStatus,
)


# Not "/{slug}": ninja pins a path's position at its first registration, and
# that pattern has to stay behind /entities and /overlay in public.py.
@router.patch(
    "/{slug}/settings",
    response={
        200: schemas.CampaignSettingsOut,
        400: ErrorResponse,
        403: ErrorResponse,
    },
    auth=AuthBearer(),
)
def patch_campaign(request, slug: str, payload: schemas.CampaignPatchRequest):
    """Rename, reschedule, or move a campaign between draft and live."""
    campaign = get_object_or_404(Campaign, slug=slug)
    if not _can_manage(request.user, campaign):
        return _denied()

    if payload.status is not None and payload.status not in (
        CampaignStatus.values
    ):
        return 400, {"detail": f"unknown status: {payload.status}"}
    start_at = payload.start_at or campaign.start_at
    end_at = payload.end_at or campaign.end_at
    if end_at <= start_at:
        return 400, {"detail": "end_at must be after start_at"}

    fields = []
    for name in ("name", "tagline", "description_md", "status"):
        value = getattr(payload, name)
        if value is not None:
            setattr(campaign, name, value)
            fields.append(name)
    campaign.start_at = start_at
    campaign.end_at = end_at
    campaign.save(update_fields=fields + ["start_at", "end_at"])
    return _settings(campaign)
