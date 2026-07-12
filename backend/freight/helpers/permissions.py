"""Permission helpers for freight admin custom views."""

from django.core.exceptions import PermissionDenied

from groups.helpers.feature_access import user_has_legacy_perm

VIEW_FREIGHT_LOCATIONS = "freight.view_evefreightroute"


def user_has_perm(user, perm: str) -> bool:
    return user_has_legacy_perm(user, perm)


def require_view_perm(user, perm: str) -> None:
    if not user_has_perm(user, perm):
        raise PermissionDenied


def index_link_perms(user, *, view_perm: str) -> dict[str, bool]:
    can_view = user_has_perm(user, view_perm)
    return {
        "add": False,
        "change": False,
        "delete": False,
        "view": can_view,
    }
