"""GET /{tribe_id}/members/{member_id}/activity - activity summary for one tribe member."""

from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
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

from eveonline.helpers.characters import (
    user_characters,
    user_primary_character,
)

from tribes.endpoints.groups.schemas import (
    CharacterRefSchema,
    TribeMemberActivityBreakdownItemSchema,
    TribeMemberActivitySchema,
)
from tribes.models import TribeGroupActivityRecord, TribeGroupMembership

PATH = "/{tribe_id}/members/{member_id}/activity"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Activity summary for one tribe member (primary + alts, total_points, record_count, breakdown).",
    "response": {200: TribeMemberActivitySchema, 404: dict},
}

router = Router(tags=["Tribes - Members"])


def _parse_since_until(since: str | None, until: str | None):
    start = end = None
    if since:
        try:
            if since.endswith("d"):
                start = timezone.now() - timedelta(days=int(since[:-1]))
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


def get_tribe_member_activity(
    request,
    tribe_id: int,
    member_id: int,
    since: str | None = Query(None),
    until: str | None = Query(None),
):
    is_member = TribeGroupMembership.objects.filter(
        tribe_group__tribe_id=tribe_id,
        user_id=member_id,
        status=TribeGroupMembership.STATUS_ACTIVE,
    ).exists()
    if not is_member:
        return 404, {"detail": "Member not found."}

    qs = TribeGroupActivityRecord.objects.filter(
        tribe_group_activity__tribe_group__tribe_id=tribe_id,
        user_id=member_id,
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
        total_points=Sum(points_expr),
    )
    record_count = agg["record_count"] or 0
    total_points = float(agg["total_points"] or 0.0)

    breakdown_qs = qs.values(
        "tribe_group_activity__activity_type",
        "tribe_group_activity__tribe_group__name",
    ).annotate(
        record_count=Count("id"),
        total_quantity=Sum("quantity"),
    )
    breakdown = [
        TribeMemberActivityBreakdownItemSchema(
            activity_type=row["tribe_group_activity__activity_type"],
            unit="",
            record_count=row["record_count"],
            total_quantity=row["total_quantity"],
        )
        for row in breakdown_qs
    ]

    user_model = get_user_model()
    try:
        user = user_model.objects.get(pk=member_id)
    except user_model.DoesNotExist:
        return 200, TribeMemberActivitySchema(
            primary_character_id=None,
            primary_character_name="",
            alts=[],
            total_points=total_points,
            record_count=record_count,
            breakdown=breakdown,
        )

    primary = user_primary_character(user)
    if primary:
        primary_character_id = primary.character_id
        primary_character_name = primary.character_name or ""
    else:
        primary_character_id = None
        primary_character_name = ""

    chars = user_characters(user)
    alts = [
        CharacterRefSchema(
            character_id=c.character_id, character_name=c.character_name or ""
        )
        for c in chars
        if not primary or c.pk != primary.pk
    ]

    return 200, TribeMemberActivitySchema(
        primary_character_id=primary_character_id,
        primary_character_name=primary_character_name,
        alts=alts,
        total_points=total_points,
        record_count=record_count,
        breakdown=breakdown,
    )


router.get(PATH, **ROUTE_SPEC)(get_tribe_member_activity)
