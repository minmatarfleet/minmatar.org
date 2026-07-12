"""Permission helpers for onboarding admin custom views."""

from django.core.exceptions import PermissionDenied

from groups.helpers.feature_access import can_use_feature, user_has_legacy_perm

VIEW_ONBOARDING = "onboarding.view_onboardingprogram"


def user_has_perm(user, perm: str) -> bool:
    return user_has_legacy_perm(user, perm)


def user_can_view_onboarding_admin(user) -> bool:
    return user_has_perm(user, VIEW_ONBOARDING) or can_use_feature(
        user, "srp.process"
    )


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
