"""GET /{tribe_id}/activity/{activity_id}/metrics - per-activity metrics for one TribeGroupActivity."""

from datetime import datetime, timedelta

from django.db.models import (
    Count,
    ExpressionWrapper,
    F,
    FloatField,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce
from django.utils import timezone
from ninja import Router, Query

from tribes.endpoints.groups.schemas import TribeActivityMetricsSchema
from tribes.models import TribeGroupActivity, TribeGroupActivityRecord

PATH = "/{tribe_id}/activity/{activity_id}/metrics"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Metrics for one tribe group activity (record count, total quantity, total points).",
    "response": {200: TribeActivityMetricsSchema, 404: dict},
}

router = Router(tags=["Tribes - Activity"])


def _parse_since_until(since: str | None, until: str | None):
    """Parse since/until query params; return (start, end) datetimes or (None, None)."""
    start = end = None
    if since:
        try:
            if since.endswith("d"):
                days = int(since[:-1])
                start = timezone.now() - timedelta(days=days)
            else:
                start = datetime.fromisoformat(since.replace("Z", "+00:00"))
                if timezone.is_naive(start):
                    start = timezone.make_aware(start)
        except (ValueError, TypeError):
            pass
    if until:
        try:
            end = datetime.fromisoformat(until.replace("Z", "+00:00"))
            if timezone.is_naive(end):
                end = timezone.make_aware(end)
        except (ValueError, TypeError):
            pass
    return start, end


def get_tribe_activity_metrics(
    request,
    tribe_id: int,
    activity_id: int,
    since: str | None = Query(None, description="ISO date or e.g. 7d, 30d"),
    until: str | None = Query(None, description="ISO date"),
):
    activity = (
        TribeGroupActivity.objects.filter(pk=activity_id)
        .select_related("tribe_group", "tribe_group__tribe")
        .first()
    )
    if not activity or activity.tribe_group.tribe_id != tribe_id:
        return 404, {"detail": "Activity not found."}

    qs = TribeGroupActivityRecord.objects.filter(
        tribe_group_activity_id=activity_id
    )
    start, end = _parse_since_until(since, until)
    if start:
        qs = qs.filter(created_at__gte=start)
    if end:
        qs = qs.filter(created_at__lte=end)

    points_expr = ExpressionWrapper(
        Coalesce(F("tribe_group_activity__points_per_record"), Value(0.0))
        + Coalesce(F("tribe_group_activity__points_per_unit"), Value(0.0))
        * Coalesce(F("quantity"), Value(0.0)),
        output_field=FloatField(),
    )
    agg = qs.aggregate(
        record_count=Count("id"),
        total_quantity=Sum("quantity"),
        total_points=Sum(points_expr),
    )
    record_count = agg["record_count"] or 0
    total_quantity = agg["total_quantity"]
    total_points = float(agg["total_points"] or 0.0)

    activity_type_labels = dict(TribeGroupActivity.ACTIVITY_TYPE_CHOICES)
    return 200, TribeActivityMetricsSchema(
        activity_id=activity.pk,
        activity_type=activity.activity_type,
        activity_type_display=activity_type_labels.get(
            activity.activity_type, activity.activity_type
        ),
        group_id=activity.tribe_group_id,
        group_name=activity.tribe_group.name or "",
        unit="",  # Could be derived from records if needed
        record_count=record_count,
        total_quantity=total_quantity,
        total_points=total_points,
    )


router.get(PATH, **ROUTE_SPEC)(get_tribe_activity_metrics)
