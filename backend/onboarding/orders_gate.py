"""Gate industry order participation APIs on current orders onboarding acknowledgment."""

from __future__ import annotations

from onboarding.models import (
    OnboardingProgram,
    OnboardingProgramType,
    UserOnboardingAcknowledgment,
)

ORDERS_ONBOARDING_PROGRAM_TYPE = OnboardingProgramType.ORDERS
ORDERS_ONBOARDING_REQUIRED_DETAIL = "orders_onboarding_required"


def user_has_current_orders_onboarding(user) -> bool:
    try:
        program = OnboardingProgram.objects.get(
            pk=ORDERS_ONBOARDING_PROGRAM_TYPE
        )
    except OnboardingProgram.DoesNotExist:
        return False
    ack = UserOnboardingAcknowledgment.objects.filter(
        user=user,
        program=program,
    ).first()
    if ack is None:
        return False
    return ack.acknowledged_version == program.version


def require_current_orders_onboarding(request):
    """Return None if allowed, else (status, body) for Ninja."""
    if user_has_current_orders_onboarding(request.user):
        return None
    return 403, {"detail": ORDERS_ONBOARDING_REQUIRED_DETAIL}
