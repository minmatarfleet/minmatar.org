from ninja import Router

from eveonline.routers.characters import router as characters_router
from eveonline.routers.corporations import router as corporations_router

router = Router(tags=["Eve Online"])
router.add_router("corporations/", corporations_router)
router.add_router("characters/", characters_router)
