"""Tribe-level endpoints (list, current, detail)."""

from ninja import Router

from tribes.endpoints.tribes.get_tribes import router as get_tribes_router
from tribes.endpoints.tribes.get_current_tribes import (
    router as get_current_tribes_router,
)
from tribes.endpoints.tribes.get_tribe import router as get_tribe_router

router = Router(tags=["Tribes"])
router.add_router("", get_tribes_router)
router.add_router("", get_current_tribes_router)
router.add_router("", get_tribe_router)

__all__ = ["router"]
