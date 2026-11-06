"""FW payout event codes, managed from campaign settings.

Registered before the ``/{slug}`` routes so ``/payout-codes`` is not read as
a campaign slug.
"""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Max
from django.utils import timezone

from app.errors import ErrorResponse
from authentication import AuthBearer
from campaigns.endpoints import schemas
from campaigns.endpoints.base import router
from campaigns.models import SiteKind
from campaigns.services.sites import rescore_completions
from eveonline.models import EveCharacterFwLpPayout, FwPayoutEventCode
from groups.helpers.feature_access import require_feature

MANAGE_FEATURE = "campaigns.manage"
PAYOUT_WINDOW_DAYS = 30


@router.get(
    "/payout-codes",
    response={200: schemas.PayoutCodesOut, 403: ErrorResponse},
    auth=AuthBearer(),
)
def list_payout_codes(request):
    """Mapped codes, plus codes seen in the last 30 days with no mapping."""
    denied = require_feature(request.user, MANAGE_FEATURE)
    if denied:
        return denied

    since = timezone.now() - timedelta(days=PAYOUT_WINDOW_DAYS)
    recent = EveCharacterFwLpPayout.objects.filter(
        occurred_at__gte=since, event_code__isnull=False
    )
    seen = {
        row["event_code"]: row["seen"]
        for row in recent.order_by()
        .values("event_code")
        .annotate(seen=Count("id"))
    }
    rows = list(FwPayoutEventCode.objects.all())
    mapped = {row.event_code for row in rows}

    unmapped = []
    for row in (
        recent.exclude(event_code__in=mapped)
        .order_by()
        .values("event_code")
        .annotate(seen=Count("id"), last_seen=Max("occurred_at"))
        .order_by("-seen")
    ):
        sample = (
            recent.filter(event_code=row["event_code"])
            .order_by("-occurred_at")
            .first()
        )
        unmapped.append(
            {
                "event_code": row["event_code"],
                "seen": row["seen"],
                "last_seen": row["last_seen"],
                "sample_amount_lp": sample.amount_lp if sample else 0,
            }
        )

    return {
        "codes": [
            {
                "event_code": row.event_code,
                "site_kind": row.site_kind,
                "label": row.label,
                "confirmed": row.confirmed,
                "confirmed_by": row.confirmed_by,
                "seen_30d": seen.get(row.event_code, 0),
            }
            for row in rows
        ],
        "unmapped": unmapped,
        "site_kinds": list(SiteKind.values),
    }


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
