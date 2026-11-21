"""One endpoint: see the function below."""

from __future__ import annotations

from django.shortcuts import get_object_or_404

from app.errors import ErrorResponse
from authentication import AuthBearer
from campaigns.endpoints import schemas, serializers
from campaigns.endpoints.base import router
from campaigns.endpoints.coordinator_helpers import _managed
from campaigns.models import CampaignFitting


@router.patch(
    "/{slug}/fittings/{row_id}",
    response={
        200: schemas.CampaignFittingOut,
        403: ErrorResponse,
        404: None,
    },
    auth=AuthBearer(),
)
def toggle_fitting(
    request,
    slug: str,
    row_id: int,
    payload: schemas.CampaignFittingToggle,
):
    """Show or hide one fitting on the campaign page."""
    campaign, denied = _managed(request, slug)
    if denied:
        return denied
    row = get_object_or_404(
        CampaignFitting.objects.select_related("fitting", "doctrine"),
        campaign=campaign,
        id=row_id,
    )
    row.enabled = payload.enabled
    row.save(update_fields=["enabled"])
    return serializers.fitting_out(row)
