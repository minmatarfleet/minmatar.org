"""Eligibility for Market Ops leaderboard / attributed-order sync."""

from eveonline.helpers.characters import user_ids_with_market_scopes
from tribes.models import TribeGroup, TribeGroupMembership

MARKET_TRIBE_GROUP_CODE = "supply.market"


def eligible_market_operator_user_ids() -> set[int]:
    """Active supply.market members who also hold a Market ESI token."""
    group = TribeGroup.objects.filter(code=MARKET_TRIBE_GROUP_CODE).first()
    if not group:
        return set()

    tribe_user_ids = set(
        TribeGroupMembership.objects.filter(
            tribe_group=group,
            status=TribeGroupMembership.STATUS_ACTIVE,
        ).values_list("user_id", flat=True)
    )
    if not tribe_user_ids:
        return set()
    return tribe_user_ids & user_ids_with_market_scopes()
