"""Permission helpers for industry admin custom views."""

from django.core.exceptions import PermissionDenied

from groups.helpers.feature_access import can_use_feature, user_has_legacy_perm

VIEW_INDUSTRY_ORDERS = "industry.view_industryorder"


def user_has_perm(user, perm: str) -> bool:
    return user_has_legacy_perm(user, perm)


def user_can_view_industry_orders_admin(user) -> bool:
    return user_has_perm(user, VIEW_INDUSTRY_ORDERS) or can_use_feature(
        user, "industry.order.submit"
    )


def require_industry_orders_admin_view(user) -> None:
    if not user_can_view_industry_orders_admin(user):
        raise PermissionDenied


def industry_orders_index_link_perms(user) -> dict[str, bool]:
    can_view = user_can_view_industry_orders_admin(user)
    return {
        "add": False,
        "change": False,
        "delete": False,
        "view": can_view,
    }
