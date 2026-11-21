from ninja import Router

from alliance.endpoints.landing.get_landing_pulse import (
    router as get_landing_pulse_router,
)

router = Router(tags=["Alliance"])
router.add_router("", get_landing_pulse_router)

__all__ = ["router"]
