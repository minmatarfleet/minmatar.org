"""GET /{program_type} — current program version and caller's acknowledgment state."""

from typing import Optional
from uuid import UUID

from ninja import Schema
from pydantic import Field

from app.errors import ErrorResponse
from authentication import AuthBearer
from onboarding.models import (
    OnboardingProgram,
    OnboardingProgramType,
    UserOnboardingAcknowledgment,
)


class OnboardingStatusResponse(Schema):
    program_type: str
    current_version: UUID
    acknowledged_version: Optional[UUID] = Field(default=None)
    is_current: bool


PATH = "{program_type}"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Onboarding status for a program (current version vs. your acknowledgment).",
    "auth": AuthBearer(),
    "response": {200: OnboardingStatusResponse, 404: ErrorResponse},
}


def get_onboarding_status(request, program_type: str):
    if program_type not in OnboardingProgramType.values:
        return 404, ErrorResponse(
            detail=f"Unknown onboarding program type '{program_type}'.",
        )
    try:
        program = OnboardingProgram.objects.get(pk=program_type)
    except OnboardingProgram.DoesNotExist:
        return 404, ErrorResponse(
            detail=f"Onboarding program '{program_type}' is not available.",
        )
    ack = UserOnboardingAcknowledgment.objects.filter(
        user=request.user,
        program=program,
    ).first()
    acknowledged_version = (
        ack.acknowledged_version if ack is not None else None
    )
    is_current = (
        acknowledged_version is not None
        and acknowledged_version == program.version
    )
    return OnboardingStatusResponse(
        program_type=program_type,
        current_version=program.version,
        acknowledged_version=acknowledged_version,
        is_current=is_current,
    )
