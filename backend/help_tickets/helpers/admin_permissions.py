"""Permission helpers for help tickets admin custom views."""

from django.core.exceptions import PermissionDenied

from groups.helpers.feature_access import user_has_legacy_perm

VIEW_HELP_TICKETS = "help_tickets.view_helpticket"


def user_has_perm(user, perm: str) -> bool:
    return user_has_legacy_perm(user, perm)


def user_can_view_help_tickets_admin(user) -> bool:
    return user_has_perm(user, VIEW_HELP_TICKETS)


def require_help_tickets_admin_view(user) -> None:
    if not user_can_view_help_tickets_admin(user):
        raise PermissionDenied


def help_tickets_index_link_perms(user) -> dict[str, bool]:
    can_view = user_can_view_help_tickets_admin(user)
    return {
        "add": False,
        "change": False,
        "delete": False,
        "view": can_view,
    }
