"""GET /character-statistics – Market Ops leaderboard by ISK on market."""

from typing import List

from ninja import Router

from market.helpers.character_statistics import (
    MarketCharacterStatResponse,
    build_market_character_statistics,
)

router = Router(tags=["Market"])


@router.get(
    "/character-statistics",
    description=(
        "Active supply.market members with a Market ESI token, ranked by "
        "total ISK on market at market-active locations."
    ),
    response=List[MarketCharacterStatResponse],
)
def get_character_statistics(request):
    return build_market_character_statistics()
