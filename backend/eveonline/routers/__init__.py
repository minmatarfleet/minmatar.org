from eveonline.routers.corporations import router as corporations_router
from eveonline.routers.characters import router as characters_router
from ninja import Router

router = Router(tags=["Eve Online"])
router.add_router("corporations/", corporations_router)
router.add_router("characters/", characters_router)
