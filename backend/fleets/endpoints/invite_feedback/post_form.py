"""Save a fleet invite feedback answer. Resubmit updates the same row."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from fleets.endpoints.invite_feedback.schemas import (
    FormResponse,
    SubmitError,
    SubmitRequest,
)
from fleets.helpers.invite_feedback import InviteFeedbackError, submit


def post_invite_feedback(request, payload: SubmitRequest):
    try:
        panel = submit(request.user, payload.model_dump())
    except InviteFeedbackError as exc:
        return exc.status_code, SubmitError(
            detail=exc.errors[0], errors=exc.errors
        )
    return FormResponse(**panel)


ROUTES = (
    (
        "post",
        "/invite-feedback",
        {
            "auth": AuthBearer(),
            "response": {
                200: FormResponse,
                400: SubmitError,
                401: ErrorResponse,
            },
            "description": (
                "Save this pilot's fleet invite feedback. A closed round "
                "returns the closed panel and does not save."
            ),
        },
        post_invite_feedback,
    ),
)
