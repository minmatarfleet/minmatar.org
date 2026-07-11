"""Permission helpers for market admin custom views."""

from django.core.exceptions import PermissionDenied

VIEW_MARKET_LOCATIONS = "market.view_evemarketitemexpectation"
VIEW_MARKET_CONTRACTS = "market.view_evemarketcontract"
VIEW_BUY_ORDER_EXPECTATIONS = "market.view_evemarketbuyorderexpectation"
VIEW_FITTING_EXPECTATIONS = "market.view_evemarketfittingexpectation"
CHANGE_FITTING_EXPECTATIONS = "market.change_evemarketfittingexpectation"
VIEW_CONTRACT_EXPECTATIONS = "market.view_evemarketcontractexpectation"
CHANGE_CONTRACT_EXPECTATIONS = "market.change_evemarketcontractexpectation"
VIEW_ITEM_EXPECTATIONS = "market.view_evemarketitemexpectation"
CHANGE_ITEM_EXPECTATIONS = "market.change_evemarketitemexpectation"


def user_has_perm(user, perm: str) -> bool:
    return user.is_active and (user.is_superuser or user.has_perm(perm))


def require_perm(user, perm: str) -> None:
    if not user_has_perm(user, perm):
        raise PermissionDenied


def require_view_perm(user, perm: str) -> None:
    require_perm(user, perm)


def require_change_perm(user, perm: str) -> None:
    require_perm(user, perm)


def index_link_perms(user, *, view_perm: str) -> dict[str, bool]:
    can_view = user_has_perm(user, view_perm)
    return {
        "add": False,
        "change": False,
        "delete": False,
        "view": can_view,
    }
