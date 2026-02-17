from ninja import Router

from eveonline.endpoints.locations.get_locations import (
    router as get_locations_router,
)

router = Router(tags=["Locations"])
router.add_router("", get_locations_router)

__all__ = ["router"]
