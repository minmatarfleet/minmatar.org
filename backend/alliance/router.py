from ninja import Router

from alliance.endpoints.health import router as health_router

router = Router(tags=["Alliance"])
router.add_router("health", health_router)

__all__ = ["router"]
