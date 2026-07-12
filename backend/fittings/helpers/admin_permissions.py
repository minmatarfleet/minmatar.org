"""Permission helpers for fittings admin custom views."""

from django.core.exceptions import PermissionDenied

from groups.helpers.feature_access import can_use_feature, user_has_legacy_perm

VIEW_EVE_FITTINGS = "fittings.view_evefitting"
CHANGE_EVE_FITTINGS = "fittings.change_evefitting"
VIEW_EVE_DOCTRINES = "fittings.view_evedoctrine"
CHANGE_EVE_DOCTRINES = "fittings.change_evedoctrine"


def user_has_perm(user, perm: str) -> bool:
    return user_has_legacy_perm(user, perm)


def user_can_view_fittings_admin(user) -> bool:
    return user.is_staff and (
        user.is_superuser
        or user_has_perm(user, VIEW_EVE_FITTINGS)
        or user_has_perm(user, CHANGE_EVE_FITTINGS)
    )


def user_can_view_doctrines_admin(user) -> bool:
    return user.is_staff and (
        user.is_superuser
        or user_has_perm(user, VIEW_EVE_DOCTRINES)
        or user_has_perm(user, CHANGE_EVE_DOCTRINES)
        or can_use_feature(user, "fittings.doctrine.propose")
        or can_use_feature(user, "fittings.doctrine.approve")
    )


def require_fittings_admin_view(user) -> None:
    if not user_can_view_fittings_admin(user):
        raise PermissionDenied


def require_doctrines_admin_view(user) -> None:
    if not user_can_view_doctrines_admin(user):
        raise PermissionDenied


def index_link_perms(user, *, can_view: bool) -> dict[str, bool]:
    return {
        "add": False,
        "change": False,
        "delete": False,
        "view": can_view,
    }
