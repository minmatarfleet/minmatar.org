"""GET "/{tribe_id}/groups/{group_id}/leaderboard" - group member leaderboard."""

from typing import List, Optional

from django.db.models import Sum
from ninja import Router

from tribes.endpoints.output.schemas import LeaderboardEntrySchema
from tribes.models import TribeActivity, TribeGroup

PATH = "/{tribe_id}/groups/{group_id}/leaderboard"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Per-member leaderboard for a tribe group, filtered by activity type.",
    "response": {200: List[LeaderboardEntrySchema], 404: dict},
}

router = Router(tags=["Tribes - Output"])


def get_group_leaderboard(
    request,
    tribe_id: int,
    group_id: int,
    activity_type: Optional[str] = None,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
):
    tg = TribeGroup.objects.filter(pk=group_id, tribe_id=tribe_id).first()
    if not tg:
        return 404, {"detail": "TribeGroup not found."}

    qs = TribeActivity.objects.filter(tribe_group=tg)
    if activity_type:
        qs = qs.filter(activity_type=activity_type)
    if period_start:
        qs = qs.filter(created_at__gte=period_start)
    if period_end:
        qs = qs.filter(created_at__lte=period_end)

    rows = (
        qs.values(
            "user_id", "character_id", "character__character_name", "unit"
        )
        .annotate(total=Sum("quantity"))
        .order_by("-total")
    )
    return 200, [
        LeaderboardEntrySchema(
            user_id=row["user_id"],
            character_id=row["character_id"],
            character_name=row.get("character__character_name"),
            total=row["total"],
            unit=row["unit"],
        )
        for row in rows
    ]


router.get(PATH, **ROUTE_SPEC)(get_group_leaderboard)
