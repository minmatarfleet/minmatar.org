from ninja import Router

from eveonline.routers.characters import router as characters_router
from eveonline.routers.corporations import router as corporations_router
from eveonline.routers.assets import router as asset_router
from eveonline.routers.players import router as player_router

router = Router(tags=["Eve Online"])
router.add_router("corporations/", corporations_router)
router.add_router("characters/", characters_router)
router.add_router("assets/", asset_router)
router.add_router("players/", player_router)
