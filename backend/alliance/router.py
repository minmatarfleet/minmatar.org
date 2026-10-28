from ninja import Router

from alliance.endpoints.health import router as health_router
from alliance.endpoints.trial import router as trial_router

router = Router(tags=["Alliance"])
router.add_router("health", health_router)
router.add_router("trial", trial_router)

__all__ = ["router"]
