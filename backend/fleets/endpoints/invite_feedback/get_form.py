"""The logged-in fleet invite feedback form."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from fleets.endpoints.invite_feedback.schemas import FormResponse
from fleets.helpers.invite_feedback import form_for


def get_invite_feedback(request, edit: bool = False):
    return FormResponse(**form_for(request.user, edit=edit))


ROUTES = (
    (
        "get",
        "/invite-feedback",
        {
            "auth": AuthBearer(),
            "response": {200: FormResponse, 401: ErrorResponse},
            "description": (
                "The fleet invite feedback form for the logged-in pilot. "
                "A pilot who was not asked gets not_invited. edit=true "
                "reopens a submitted form while the round is open."
            ),
        },
        get_invite_feedback,
    ),
)
