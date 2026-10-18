"""GET /character-statistics – completed contracts in last 30 days by primary character."""

from collections import Counter
from datetime import timedelta
from typing import List

from django.utils import timezone
from ninja import Router

from eveonline.helpers.characters.identity import (
    owner_user_ids,
    primary_refs_for_users,
)
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

    char_to_user = owner_user_ids(acceptor_ids)

    user_counts: Counter = Counter()
    for c in contracts:
        user_id = char_to_user.get(c.acceptor_id)
        if user_id:
            user_counts[user_id] += 1

    if not user_counts:
        return []

    primary_by_user = primary_refs_for_users(user_counts)

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
