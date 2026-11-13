"""Eligibility for the Market Ops leaderboard."""

from eveonline.helpers.characters import user_ids_with_market_scopes


def eligible_market_operator_user_ids() -> set[int]:
    """Users with a Market ESI token, whose stock Market ops can attribute."""
    return user_ids_with_market_scopes()
