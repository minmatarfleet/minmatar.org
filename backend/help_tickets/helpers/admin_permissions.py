"""Permission helpers for help tickets admin custom views."""

from django.core.exceptions import PermissionDenied

VIEW_HELP_TICKETS = "help_tickets.view_helprequestcategory"


def user_has_perm(user, perm: str) -> bool:
    return user.is_active and (user.is_superuser or user.has_perm(perm))


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
