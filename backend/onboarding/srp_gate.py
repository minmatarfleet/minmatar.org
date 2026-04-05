"""Gate SRP pilot-facing API endpoints on current SRP onboarding acknowledgment."""

from __future__ import annotations

from django.contrib.auth.models import AnonymousUser

from onboarding.models import (
    OnboardingProgram,
    OnboardingProgramType,
    UserOnboardingAcknowledgment,
)

SRP_ONBOARDING_PROGRAM_TYPE = OnboardingProgramType.SRP
SRP_ONBOARDING_REQUIRED_DETAIL = "srp_onboarding_required"


def bypass_srp_onboarding(user) -> bool:
    if user is None or isinstance(user, AnonymousUser):
        return False
    # Superusers have all perms in Django; only explicit assignees skip pilot onboarding.
    if getattr(user, "is_superuser", False):
        return False
    return user.has_perm("srp.change_evefleetshipreimbursement")


def user_has_current_srp_onboarding(user) -> bool:
    if bypass_srp_onboarding(user):
        return True
    try:
        program = OnboardingProgram.objects.get(pk=SRP_ONBOARDING_PROGRAM_TYPE)
    except OnboardingProgram.DoesNotExist:
        # Misconfigured DB — do not treat as "onboarded"; block pilot-facing SRP actions.
        return False
    ack = UserOnboardingAcknowledgment.objects.filter(
        user=user,
        program=program,
    ).first()
    if ack is None:
        return False
    return ack.acknowledged_version == program.version


def require_current_srp_onboarding(request):
    """Return None if allowed, else (status, body) for Ninja."""
    if user_has_current_srp_onboarding(request.user):
        return None
    return 403, {"detail": SRP_ONBOARDING_REQUIRED_DETAIL}
