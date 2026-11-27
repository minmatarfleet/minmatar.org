"""POST "/exit/{token}" - answer the survey behind a mailed link. No login."""

from app.errors import ErrorResponse
from surveys.endpoints.get_exit_survey import GONE
from surveys.endpoints.schemas import (
    ExitSurveySubmitRequest,
    ExitSurveySubmitResponse,
)
from surveys.helpers import exit_tokens
from surveys.helpers.exit_answers import ExitAnswerError, submit

PATH = "/exit/{token}"
METHOD = "post"
ROUTE_SPEC = {
    "tags": ["Surveys"],
    "response": {
        201: ExitSurveySubmitResponse,
        400: ErrorResponse,
        404: ErrorResponse,
        410: ErrorResponse,
    },
    "auth": None,
    "summary": "Answer an exit or alliance move survey (no login, once)",
}


def post_exit_survey(
    request, token: str, payload: ExitSurveySubmitRequest
):  # pylint: disable=unused-argument
    try:
        invite = exit_tokens.invite_for(token)
    except exit_tokens.TokenInvalid:
        return 404, ErrorResponse(detail=GONE)
    except exit_tokens.TokenGone:
        return 410, ErrorResponse(detail=GONE)
    answers = {a.question_key: a.value for a in payload.answers}
    try:
        submit(invite, answers)
    except ExitAnswerError as error:
        if error.message == "used":
            return 410, ErrorResponse(detail=GONE)
        return 400, ErrorResponse(detail=error.message)
    return 201, {"ok": True}
