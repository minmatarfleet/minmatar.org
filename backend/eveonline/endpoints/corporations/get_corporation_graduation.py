"""GET /corporations/{corporation_id}/graduation - the Academy's graduation
pipeline. 404 for any corporation but the Academy."""

from ninja import Router

from app.errors import ErrorResponse
from applications import graduation
from authentication import AuthBearer
from eveonline.endpoints.corporations.schemas import AcademyGraduationPipeline
from eveonline.helpers.corporations.graduation_payload import (
    load_academy,
    pilot_out,
)
from eveonline.helpers.corporations.permissions import (
    can_review_academy_graduation,
    can_view_academy_graduation,
)

router = Router(tags=["Corporations"])


@router.get(
    "corporations/{corporation_id}/graduation",
    response={
        200: AcademyGraduationPipeline,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    auth=AuthBearer(),
    summary="The Academy's graduation pipeline (Academy leadership only)",
)
def get_corporation_graduation(request, corporation_id: int):
    corporation = load_academy(corporation_id)
    if corporation is None:
        return 404, ErrorResponse(detail="Not the Academy")
    if not can_view_academy_graduation(request.user, corporation):
        return 403, ErrorResponse(detail="Not authorised")
    corporations = graduation.graduate_corporations()
    tickers = {c.ticker: c.corporation_id for c in corporations}
    return {
        "bar": {
            "review_after_days": graduation.REVIEW_AFTER_DAYS,
            "fleets": graduation.BAR_FLEETS,
            "kills": graduation.BAR_KILLS,
            "voice_hours": graduation.BAR_VOICE_HOURS,
            "voice_kills": graduation.BAR_VOICE_KILLS,
        },
        "can_review": can_review_academy_graduation(request.user, corporation),
        "pilots": [
            pilot_out(pilot, tickers)
            for pilot in graduation.pipeline_pilots(corporation)
        ],
        "graduates": graduation.recent_graduates(corporation),
        "corporations": [
            {
                "corporation_id": c.corporation_id,
                "name": c.name,
                "ticker": c.ticker,
            }
            for c in corporations
        ],
    }
