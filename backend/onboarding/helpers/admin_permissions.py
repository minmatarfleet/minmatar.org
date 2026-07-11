"""Permission helpers for onboarding admin custom views."""

from django.core.exceptions import PermissionDenied

VIEW_ONBOARDING = "onboarding.view_onboardingprogram"


def user_has_perm(user, perm: str) -> bool:
    return user.is_active and (user.is_superuser or user.has_perm(perm))


def user_can_view_onboarding_admin(user) -> bool:
    return user_has_perm(user, VIEW_ONBOARDING)


def require_onboarding_admin_view(user) -> None:
    if not user_can_view_onboarding_admin(user):
        raise PermissionDenied


def onboarding_index_link_perms(user) -> dict[str, bool]:
    can_view = user_can_view_onboarding_admin(user)
    return {
        "add": False,
        "change": False,
        "delete": False,
        "view": can_view,
    }
