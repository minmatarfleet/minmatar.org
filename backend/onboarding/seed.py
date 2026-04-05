"""Ensure a DB row exists for every defined OnboardingProgramType."""

import uuid

from onboarding.models import OnboardingProgram, OnboardingProgramType


def ensure_onboarding_programs() -> None:
    """Idempotent: called from AppConfig.ready() after migrations."""
    for program_type in OnboardingProgramType:
        OnboardingProgram.objects.get_or_create(
            program_type=program_type,
            defaults={"version": uuid.uuid4()},
        )
