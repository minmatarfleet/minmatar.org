"""GET "/applications/{application_id}/history" - for the corporation's recruiters."""

from dataclasses import asdict

from app.errors import ErrorResponse
from applications.models import EveCorporationApplication
from authentication import AuthBearer
from eveonline.helpers.corporations.applications import can_review_applications
from eveonline.models import EveCorporation
from exits.endpoints.schemas import HistoryEntryResponse
from exits.helpers.history import history_for

PATH = "/applications/{int:application_id}/history"
METHOD = "get"
ROUTE_SPEC = {
    "tags": ["Exits"],
    "response": {
        200: list[HistoryEntryResponse],
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "An applicant's alliance history (the corporation's recruiters only)",
}


def get_application_history(request, application_id: int):
    application = (
        EveCorporationApplication.objects.select_related("user")
        .filter(pk=application_id)
        .first()
    )
    if application is None:
        return 404, ErrorResponse(detail="Application not found")
    corporation = EveCorporation.objects.filter(
        corporation_id=application.corporation_id
    ).first()
    # The applicant can open their own application: never show it to them.
    if (
        corporation is None
        or application.user_id == request.user.id
        or not can_review_applications(request.user, corporation)
    ):
        return 403, ErrorResponse(
            detail="Only the corporation's recruiters can see this"
        )
    return 200, [asdict(entry) for entry in history_for(application.user, [])]
