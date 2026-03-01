"""GET "/{tribe_id}/groups/{group_id}/output" - per-group output summary."""

from typing import Optional

from django.db.models import Sum
from ninja import Router

from tribes.endpoints.output.schemas import GroupOutputSummarySchema
from tribes.models import TribeActivity, TribeGroup

PATH = "/{tribe_id}/groups/{group_id}/output"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Output summary for a specific tribe group.",
    "response": {200: GroupOutputSummarySchema, 404: dict},
}

router = Router(tags=["Tribes - Output"])


def get_group_output(
    request,
    tribe_id: int,
    group_id: int,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
):
    tg = TribeGroup.objects.filter(pk=group_id, tribe_id=tribe_id).first()
    if not tg:
        return 404, {"detail": "TribeGroup not found."}

    qs = TribeActivity.objects.filter(tribe_group=tg)
    if period_start:
        qs = qs.filter(created_at__gte=period_start)
    if period_end:
        qs = qs.filter(created_at__lte=period_end)

    totals: dict = {}
    for row in (
        qs.values("activity_type", "unit")
        .annotate(total=Sum("quantity"))
        .order_by("activity_type")
    ):
        key = f"{row['activity_type']} ({row['unit']})"
        totals[key] = row["total"]

    return 200, GroupOutputSummarySchema(
        tribe_group_id=tg.pk,
        tribe_group_name=str(tg),
        tribe_id=tg.tribe_id,
        period_start=period_start,
        period_end=period_end,
        totals=totals,
    )


router.get(PATH, **ROUTE_SPEC)(get_group_output)
