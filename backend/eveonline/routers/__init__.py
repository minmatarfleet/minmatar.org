"""Register all eveonline endpoints. app/urls.py mounts this router at eveonline/."""

from ninja import Router

from eveonline.endpoints.characters import router as characters_router
from eveonline.endpoints.characters.assets import router as asset_router
from eveonline.endpoints.characters.players import router as player_router
from eveonline.endpoints.corporations import router as corporations_router
from eveonline.endpoints.locations import router as locations_router

router = Router(tags=["Eve Online"])
router.add_router("corporations/", corporations_router)
router.add_router("characters/", characters_router)
router.add_router("assets/", asset_router)
router.add_router("players/", player_router)
router.add_router("locations/", locations_router)

__all__ = ["router"]
