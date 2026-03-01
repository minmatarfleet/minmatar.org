"""GET "/output" - cross-tribe output summary."""

from typing import List, Optional

from django.db.models import Sum
from ninja import Router

from tribes.endpoints.output.schemas import GroupOutputSummarySchema
from tribes.models import TribeActivity, TribeGroup

PATH = "/output"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Cross-tribe output summary, optionally filtered by date range.",
    "response": {200: List[GroupOutputSummarySchema]},
}

router = Router(tags=["Tribes - Output"])


def get_output(
    request,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
):
    qs = TribeActivity.objects.all()
    if period_start:
        qs = qs.filter(created_at__gte=period_start)
    if period_end:
        qs = qs.filter(created_at__lte=period_end)

    result = []
    for tg in TribeGroup.objects.filter(is_active=True).select_related(
        "tribe"
    ):
        group_qs = qs.filter(tribe_group=tg)
        totals: dict = {}
        for row in (
            group_qs.values("activity_type", "unit")
            .annotate(total=Sum("quantity"))
            .order_by("activity_type")
        ):
            key = f"{row['activity_type']} ({row['unit']})"
            totals[key] = row["total"]

        result.append(
            GroupOutputSummarySchema(
                tribe_group_id=tg.pk,
                tribe_group_name=str(tg),
                tribe_id=tg.tribe_id,
                period_start=period_start,
                period_end=period_end,
                totals=totals,
            )
        )
    return result


router.get(PATH, **ROUTE_SPEC)(get_output)
