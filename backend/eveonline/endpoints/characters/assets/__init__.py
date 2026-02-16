from ninja import Router

from eveonline.endpoints.characters.assets.get_ships import (
    router as get_ships_router,
)

router = Router(tags=["Assets"])
router.add_router("ships", get_ships_router)

__all__ = ["router"]
