"""POST /corporations/{corporation_id}/graduation/reviews - record a
graduation decision for an Academy pilot. 404 for any corporation but the
Academy."""

from ninja import Router

from app.errors import ErrorResponse
from applications import graduation
from authentication import AuthBearer
from eveonline.endpoints.corporations.schemas import (
    AcademyGraduationReviewOut,
    AcademyGraduationReviewRequest,
)
from eveonline.helpers.corporations.graduation_payload import (
    load_academy,
    review_out,
)
from eveonline.helpers.corporations.permissions import (
    can_review_academy_graduation,
)

router = Router(tags=["Corporations"])


@router.post(
    "corporations/{corporation_id}/graduation/reviews",
    response={
        201: AcademyGraduationReviewOut,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    auth=AuthBearer(),
    summary="Record a graduation decision for an Academy pilot",
)
def post_corporation_graduation_review(
    request, corporation_id: int, payload: AcademyGraduationReviewRequest
):
    corporation = load_academy(corporation_id)
    if corporation is None:
        return 404, ErrorResponse(detail="Not the Academy")
    if not can_review_academy_graduation(request.user, corporation):
        return 403, ErrorResponse(detail="Not authorised")
    result = graduation.record_review(
        corporation,
        request.user,
        payload.character_id,
        payload.decision,
        payload.corporation_ids,
        payload.note,
    )
    if isinstance(result, str):
        return 400, ErrorResponse(detail=result)
    return 201, review_out(result)
