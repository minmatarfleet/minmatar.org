"""GET /api/alliance/landing/week - "The week in the alliance", paginated."""

from ninja import Router

from alliance.endpoints.landing.schemas import LandingWeekResponse
from alliance.helpers.landing_week import landing_week

router = Router(tags=["Alliance"])


@router.get(
    "week",
    response={200: LandingWeekResponse},
    auth=None,
    summary="The last 7 days for the new landing page, 12 rows a page",
)
def get_landing_week(request, tab: str = "fights", page: int = 1):
    return 200, landing_week(tab, page)
