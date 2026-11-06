"""One endpoint: see the function below."""

from __future__ import annotations


from django.shortcuts import get_object_or_404

from app.errors import ErrorResponse
from authentication import AuthBearer

from campaigns.endpoints import schemas, serializers
from campaigns.endpoints.base import router
from campaigns.endpoints.manage import _can_manage, _denied
from campaigns.models import (
    Campaign,
    CampaignFitting,
)
from fittings.models import EveFitting


@router.post(
    "/{slug}/fittings",
    response={
        200: schemas.CampaignFittingOut,
        400: ErrorResponse,
        403: ErrorResponse,
    },
    auth=AuthBearer(),
)
def add_fitting(request, slug: str, payload: schemas.FittingAddRequest):
    campaign = get_object_or_404(Campaign, slug=slug)
    if not _can_manage(request.user, campaign):
        return _denied()
    fitting = EveFitting.objects.filter(id=payload.fitting_id).first()
    if not fitting:
        return 400, {"detail": f"unknown fitting id: {payload.fitting_id}"}
    row, _ = CampaignFitting.objects.update_or_create(
        campaign=campaign,
        fitting=fitting,
        defaults={
            "role_label": payload.role_label,
            "srp_eligible": payload.srp_eligible,
        },
    )
    return serializers.fitting_out(row)
