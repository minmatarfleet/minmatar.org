"""POST /{program_type}/ack — record acknowledgment at the program's current version."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from onboarding.models import (
    OnboardingProgram,
    OnboardingProgramType,
    UserOnboardingAcknowledgment,
)

PATH = "{program_type}/ack"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Acknowledge the current onboarding content for a program.",
    "auth": AuthBearer(),
    "response": {204: None, 404: ErrorResponse},
}


def post_onboarding_ack(request, program_type: str):
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
    UserOnboardingAcknowledgment.objects.update_or_create(
        user=request.user,
        program=program,
        defaults={"acknowledged_version": program.version},
    )
    return 204, None
