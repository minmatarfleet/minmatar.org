"""GET /api/alliance/landing/pulse - the new landing page's heartbeat."""

from ninja import Router

from alliance.endpoints.landing.schemas import LandingPulseResponse
from alliance.helpers.landing_pulse import landing_pulse
from app.errors import ErrorResponse
from authentication import AuthBearer

router = Router(tags=["Alliance"])


@router.get(
    "pulse",
    response={200: LandingPulseResponse, 403: ErrorResponse},
    auth=AuthBearer(),
    summary="Alliance activity for the new landing page, 60 minutes behind",
)
def get_landing_pulse(request):
    # Superusers only while /landing-new is a preview: the feed names
    # pilots, and the opt-out for that is not built yet.
    if not request.user.is_superuser:
        return 403, ErrorResponse(detail="Superuser only")
    return 200, landing_pulse()
