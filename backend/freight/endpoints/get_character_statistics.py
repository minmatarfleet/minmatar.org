"""GET /character-statistics – completed contracts in last 30 days by primary character."""

from datetime import timedelta
from typing import List

from django.db.models import Count
from django.utils import timezone
from ninja import Router

from eveonline.models import EvePlayer
from freight.models import EveFreightContract
from freight.endpoints.schemas import FreightCharacterStatResponse

router = Router(tags=["Freight"])


@router.get(
    "/character-statistics",
    description="Fetch character statistics: users with completed freight contracts in the past 30 days, keyed by primary character.",
    response=List[FreightCharacterStatResponse],
)
def get_character_statistics(request):
    since = timezone.now() - timedelta(days=30)
    # Completed (finished) contracts in window, grouped by completed_by (User)
    aggregates = (
        EveFreightContract.objects.filter(
            status="finished",
            date_completed__gte=since,
            completed_by_id__isnull=False,
        )
        .values("completed_by_id")
        .annotate(completed_contracts_count=Count("id"))
    )
    user_ids = [row["completed_by_id"] for row in aggregates]
    count_by_user = {
        row["completed_by_id"]: row["completed_contracts_count"]
        for row in aggregates
    }

    if not user_ids:
        return []

    # Resolve primary character per user (EvePlayer.primary_character)
    players = (
        EvePlayer.objects.filter(user_id__in=user_ids)
        .select_related("primary_character")
        .only(
            "user_id",
            "primary_character_id",
            "primary_character__character_id",
            "primary_character__character_name",
        )
    )
    primary_by_user = {}
    for p in players:
        if p.primary_character_id:
            primary_by_user[p.user_id] = (
                p.primary_character.character_id,
                p.primary_character.character_name or "",
            )

    result = []
    for user_id in user_ids:
        count = count_by_user[user_id]
        primary = primary_by_user.get(user_id)
        if primary:
            char_id, char_name = primary
            result.append(
                FreightCharacterStatResponse(
                    primary_character_id=char_id,
                    primary_character_name=char_name or None,
                    completed_contracts_count=count,
                )
            )
        else:
            result.append(
                FreightCharacterStatResponse(
                    primary_character_id=None,
                    primary_character_name=None,
                    completed_contracts_count=count,
                )
            )
    # Sort by completed count descending, then by primary name
    result.sort(
        key=lambda r: (
            -r.completed_contracts_count,
            (r.primary_character_name or "").lower(),
        )
    )
    return result
