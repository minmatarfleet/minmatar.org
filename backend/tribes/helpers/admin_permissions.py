"""Permission helpers for tribes admin custom views."""

from django.core.exceptions import PermissionDenied

from groups.helpers.feature_access import can_use_feature, user_has_legacy_perm

VIEW_TRIBES = "tribes.view_tribe"
VIEW_TRIBE_GROUPS = "tribes.view_tribegroup"


def user_has_perm(user, perm: str) -> bool:
    return user_has_legacy_perm(user, perm)


def user_can_view_tribes_admin(user) -> bool:
    return (
        user_has_perm(user, VIEW_TRIBES)
        or user_has_perm(user, VIEW_TRIBE_GROUPS)
        or can_use_feature(user, "tribes.manage_memberships")
    )


def require_perm(user, perm: str) -> None:
    if not user_has_perm(user, perm):
        raise PermissionDenied


def require_tribes_admin_view(user) -> None:
    if not user_can_view_tribes_admin(user):
        raise PermissionDenied


def require_view_perm(user, perm: str) -> None:
    require_perm(user, perm)


def index_link_perms(user, *, view_perm: str) -> dict[str, bool]:
    can_view = user_has_perm(user, view_perm)
    return {
        "add": False,
        "change": False,
        "delete": False,
        "view": can_view,
    }


def tribes_index_link_perms(user) -> dict[str, bool]:
    can_view = user_can_view_tribes_admin(user)
    return {
        "add": False,
        "change": False,
        "delete": False,
        "view": can_view,
    }
