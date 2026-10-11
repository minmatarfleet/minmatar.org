"""Leadership gate for survey management, wrapping the groups feature system."""

from groups.helpers.feature_access import can_use_feature

from surveys.constants import FEATURE_MANAGE


def can_manage_surveys(user) -> bool:
    if user is None:
        return False
    if getattr(user, "is_superuser", False):
        return True
    return can_use_feature(user, FEATURE_MANAGE)


def require_manage(request):
    """Return (403, body) tuple for a Ninja endpoint, or None if allowed."""
    if can_manage_surveys(request.user):
        return None
    return 403, {"detail": "You do not have permission to manage surveys."}


def require_superuser(request):
    """Results viewing is restricted to superusers only."""
    if getattr(request.user, "is_superuser", False):
        return None
    return 403, {"detail": "Only superusers may view survey results."}
