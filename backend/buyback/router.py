from ninja import Router

from buyback.endpoints import router as endpoints_router

router = Router(tags=["Buyback"])
router.add_router("", endpoints_router)
