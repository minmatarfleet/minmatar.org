"""One endpoint: see the function below."""

from __future__ import annotations


from django.utils import timezone

from app.errors import ErrorResponse
from authentication import AuthBearer

from campaigns.endpoints import schemas
from campaigns.endpoints.base import router
from campaigns.models import (
    SiteKind,
)
from campaigns.services.sites import rescore_completions
from eveonline.models import FwPayoutEventCode
from groups.helpers.feature_access import require_feature

MANAGE_FEATURE = "campaigns.manage"


@router.put(
    "/payout-codes/{event_code}",
    response={
        200: schemas.PayoutCodeOut,
        400: ErrorResponse,
        403: ErrorResponse,
    },
    auth=AuthBearer(),
)
def set_payout_code(
    request, event_code: int, payload: schemas.PayoutCodeRequest
):
    """Add a code or change its complex type and whether it counts.

    Counting a code rescores the sites already recorded under it, the same
    as ``manage.py confirm_fw_event_code``.
    """
    denied = require_feature(request.user, MANAGE_FEATURE)
    if denied:
        return denied
    if payload.site_kind not in SiteKind.values:
        return 400, {"detail": f"unknown site kind: {payload.site_kind}"}

    row, _ = FwPayoutEventCode.objects.get_or_create(event_code=event_code)
    was_confirmed = row.confirmed
    row.site_kind = payload.site_kind
    row.label = payload.label
    row.confirmed = payload.confirmed
    if payload.confirmed and not was_confirmed:
        row.confirmed_by = request.user.username
        row.confirmed_at = timezone.now()
    elif not payload.confirmed:
        row.confirmed_by = ""
        row.confirmed_at = None
    row.save()
    rescore_completions(event_code=event_code)

    return {
        "event_code": row.event_code,
        "site_kind": row.site_kind,
        "label": row.label,
        "confirmed": row.confirmed,
        "confirmed_by": row.confirmed_by,
        "seen_30d": 0,
    }
