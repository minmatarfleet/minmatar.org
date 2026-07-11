"""Permission helpers for fittings admin custom views."""

from django.core.exceptions import PermissionDenied

VIEW_EVE_FITTINGS = "fittings.view_evefitting"
CHANGE_EVE_FITTINGS = "fittings.change_evefitting"
VIEW_EVE_DOCTRINES = "fittings.view_evedoctrine"
CHANGE_EVE_DOCTRINES = "fittings.change_evedoctrine"


def user_has_perm(user, perm: str) -> bool:
    return user.is_active and (user.is_superuser or user.has_perm(perm))


def user_can_view_fittings_admin(user) -> bool:
    return user.is_staff and (
        user.is_superuser
        or user.has_perm(VIEW_EVE_FITTINGS)
        or user.has_perm(CHANGE_EVE_FITTINGS)
    )


def user_can_view_doctrines_admin(user) -> bool:
    return user.is_staff and (
        user.is_superuser
        or user.has_perm(VIEW_EVE_DOCTRINES)
        or user.has_perm(CHANGE_EVE_DOCTRINES)
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
