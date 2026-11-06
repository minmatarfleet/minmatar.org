"""One endpoint: see the function below."""

from __future__ import annotations


from datetime import timedelta
from django.db.models import Count, Max
from django.utils import timezone

from app.errors import ErrorResponse
from authentication import AuthBearer

from campaigns.endpoints import schemas
from campaigns.endpoints.base import router
from campaigns.models import (
    SiteKind,
)
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
