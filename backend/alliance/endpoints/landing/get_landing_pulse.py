"""GET /api/alliance/landing/pulse - the new landing page's heartbeat."""

from ninja import Router

from alliance.endpoints.landing.schemas import LandingPulseResponse
from alliance.helpers.landing_pulse import landing_pulse

router = Router(tags=["Alliance"])


@router.get(
    "pulse",
    response={200: LandingPulseResponse},
    auth=None,
    summary="Alliance activity for the new landing page (public)",
)
def get_landing_pulse(request):
    # Public: /landing-new is open to everyone at its hidden URL. Kills and
    # sites are live; fleets and comms in the totals stay an hour behind.
    return 200, landing_pulse()
