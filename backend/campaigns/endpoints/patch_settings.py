"""One endpoint: see the function below."""

from __future__ import annotations


from django.shortcuts import get_object_or_404
from django.utils import timezone

from app.errors import ErrorResponse
from authentication import AuthBearer

from campaigns.endpoints import schemas
from campaigns.endpoints.base import router
from campaigns.endpoints.manage import _can_manage, _denied
from campaigns.endpoints.settings_helpers import _settings
from campaigns.models import (
    COORDINATOR_SCOPES,
    Campaign,
    CampaignStatus,
    feature_field,
)


def _track_pause(campaign: Campaign, status: str, fields: list) -> None:
    """Stamp when a campaign pauses; clear it when it leaves the pause."""
    paused = status == CampaignStatus.PAUSED
    if paused and campaign.paused_at is None:
        campaign.paused_at = timezone.now()
        fields.append("paused_at")
    elif not paused and campaign.paused_at is not None:
        campaign.paused_at = None
        fields.append("paused_at")


def _apply_disclosure(campaign: Campaign, payload, fields: list) -> str:
    """Undisclose or disclose, and set what coordinators see. Returns an
    error message, or "" when the payload is fine."""
    if payload.undisclosed is not None:
        campaign.undisclosed = payload.undisclosed
        fields.append("undisclosed")
    if payload.coordinator_scopes is not None:
        unknown = set(payload.coordinator_scopes) - set(COORDINATOR_SCOPES)
        if unknown:
            return f"unknown scopes: {sorted(unknown)}"
        campaign.coordinator_scopes = [
            scope
            for scope in COORDINATOR_SCOPES
            if scope in payload.coordinator_scopes
        ]
        fields.append("coordinator_scopes")
    return ""


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
    """Rename, reschedule, switch features, or move a campaign between
    draft and live."""
    campaign = get_object_or_404(Campaign, slug=slug)
    if not _can_manage(request.user, campaign):
        return _denied()

    if payload.status is not None and payload.status not in (
        CampaignStatus.values
    ):
        return 400, {"detail": f"unknown status: {payload.status}"}
    if (
        payload.status == CampaignStatus.PAUSED
        and campaign.status != CampaignStatus.PAUSED
        and not campaign.is_faction_warfare
    ):
        return 400, {"detail": "Only faction warfare campaigns can pause."}
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
    if payload.status is not None:
        _track_pause(campaign, payload.status, fields)
    if payload.features is not None:
        for feature, value in payload.features.dict().items():
            if value is not None:
                setattr(campaign, feature_field(feature), value)
                fields.append(feature_field(feature))
    error = _apply_disclosure(campaign, payload, fields)
    if error:
        return 400, {"detail": error}
    campaign.start_at = start_at
    campaign.end_at = end_at
    campaign.save(update_fields=fields + ["start_at", "end_at"])
    return _settings(campaign)
