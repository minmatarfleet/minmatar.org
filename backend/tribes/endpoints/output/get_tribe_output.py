"""GET "/{tribe_id}/output" - per-tribe output summary."""

from typing import List, Optional

from django.db.models import Sum
from ninja import Router

from tribes.endpoints.output.schemas import GroupOutputSummarySchema
from tribes.models import Tribe, TribeActivity

PATH = "/{tribe_id}/output"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Output summary for all groups in a tribe.",
    "response": {200: List[GroupOutputSummarySchema], 404: dict},
}

router = Router(tags=["Tribes - Output"])


def get_tribe_output(
    request,
    tribe_id: int,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
):
    tribe = Tribe.objects.filter(pk=tribe_id).first()
    if not tribe:
        return 404, {"detail": "Tribe not found."}

    qs = TribeActivity.objects.filter(tribe_group__tribe=tribe)
    if period_start:
        qs = qs.filter(created_at__gte=period_start)
    if period_end:
        qs = qs.filter(created_at__lte=period_end)

    result = []
    for tg in tribe.groups.filter(is_active=True):
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
                tribe_id=tribe.pk,
                period_start=period_start,
                period_end=period_end,
                totals=totals,
            )
        )
    return 200, result


router.get(PATH, **ROUTE_SPEC)(get_tribe_output)
