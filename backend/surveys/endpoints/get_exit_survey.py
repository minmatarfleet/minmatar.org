"""GET "/exit/{token}" - the survey behind a mailed link. No login."""

from app.errors import ErrorResponse
from surveys.endpoints.schemas import ExitSurveyFormResponse
from surveys.helpers import exit_tokens
from surveys.helpers.exit_answers import survey_form

GONE = "This link has already been used or has expired."


PATH = "/exit/{token}"
METHOD = "get"
ROUTE_SPEC = {
    "tags": ["Surveys"],
    "response": {
        200: ExitSurveyFormResponse,
        404: ErrorResponse,
        410: ErrorResponse,
    },
    "auth": None,
    "summary": "An exit or alliance move survey, from its link (no login)",
}


def get_exit_survey(request, token: str):  # pylint: disable=unused-argument
    try:
        invite = exit_tokens.invite_for(token)
    except exit_tokens.TokenInvalid:
        return 404, ErrorResponse(detail=GONE)
    except exit_tokens.TokenGone:
        return 410, ErrorResponse(detail=GONE)
    return 200, survey_form(invite)
