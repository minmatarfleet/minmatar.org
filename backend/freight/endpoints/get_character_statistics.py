"""GET /character-statistics – completed contracts in last 30 days by primary character."""

from collections import Counter
from datetime import timedelta
from typing import List

from django.utils import timezone
from ninja import Router

from eveonline.models import EveCharacter, EvePlayer
from freight.models import FreightContract, FREIGHT_CORPORATION_ID
from freight.endpoints.schemas import FreightCharacterStatResponse

router = Router(tags=["Freight"])


@router.get(
    "/character-statistics",
    description="Fetch character statistics: users with completed freight contracts in the past 30 days, keyed by primary character.",
    response=List[FreightCharacterStatResponse],
)
def get_character_statistics(request):
    since = timezone.now() - timedelta(days=30)

    contracts = (
        FreightContract.objects.finished()
        .filter(
            date_completed__gte=since,
            acceptor_id__isnull=False,
        )
        .exclude(
            acceptor_id=FREIGHT_CORPORATION_ID,
        )
    )

    acceptor_ids = set(contracts.values_list("acceptor_id", flat=True))
    if not acceptor_ids:
        return []

    chars = EveCharacter.objects.filter(
        character_id__in=acceptor_ids,
    ).select_related("user", "token__user")
    char_to_user = {}
    for char in chars:
        user = char.user or (
            char.token.user if getattr(char, "token", None) else None
        )
        if user:
            char_to_user[char.character_id] = user

    user_counts: Counter = Counter()
    for c in contracts:
        user = char_to_user.get(c.acceptor_id)
        if user:
            user_counts[user.id] += 1

    if not user_counts:
        return []

    user_ids = list(user_counts.keys())
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
    for user_id, count in user_counts.items():
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

    result.sort(
        key=lambda r: (
            -r.completed_contracts_count,
            (r.primary_character_name or "").lower(),
        )
    )
    return result
