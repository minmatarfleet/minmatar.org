"""GET /corporations/{corporation_id}/applications/open."""

from typing import List

from ninja import Router

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.endpoints.corporations.schemas import (
    CorporationOpenApplication,
)
from eveonline.helpers.corporations.applications import (
    can_review_applications,
    outstanding_applications,
)
from eveonline.helpers.corporations.profile import load_corporation

router = Router(tags=["Corporations"])


@router.get(
    "corporations/{corporation_id}/applications/open",
    response={
        200: List[CorporationOpenApplication],
        403: ErrorResponse,
        404: ErrorResponse,
    },
    auth=AuthBearer(),
    summary="Outstanding corporation applications for reviewers",
)
def get_open_corporation_applications(request, corporation_id: int):
    corporation = load_corporation(corporation_id)
    if corporation is None:
        return 404, ErrorResponse(detail="Corporation not found")
    if not can_review_applications(request.user, corporation):
        return 403, ErrorResponse(detail="Not authorised")
    return outstanding_applications(corporation.corporation_id)
