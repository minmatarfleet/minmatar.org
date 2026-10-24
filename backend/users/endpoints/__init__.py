from ninja import Router

from users.endpoints.get_me_gates import router as get_me_gates_router

router = Router(tags=["Authentication"])
router.add_router("", get_me_gates_router)

__all__ = ["router"]
