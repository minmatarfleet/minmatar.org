"""Counts for Strategic FCs. No names, fleet ids, or private objectives."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from fleets.endpoints.invite_feedback.schemas import ResultsResponse
from fleets.helpers.invite_feedback_results import results_payload
from groups.helpers.feature_access import can_use_feature


def get_invite_feedback_results(request, cut: str = "all", link: bool = False):
    if not can_use_feature(request.user, "fleets.manage_any"):
        return 403, ErrorResponse(detail="Only Strategic FCs can see this.")
    return ResultsResponse(**results_payload(cut, link_only=link))


ROUTES = (
    (
        "get",
        "/invite-feedback/results",
        {
            "auth": AuthBearer(),
            "response": {
                200: ResultsResponse,
                403: ErrorResponse,
                401: ErrorResponse,
            },
            "description": (
                "Fleet invite feedback counts for Strategic FCs. "
                "link=true only says whether a round exists, for the "
                "schedule page. A cut with fewer than 5 answers is omitted."
            ),
        },
        get_invite_feedback_results,
    ),
)
