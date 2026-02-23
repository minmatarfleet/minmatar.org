"""Blueprints router: GET originals and GET copies with owner/primary character in SQL."""

from ninja import Router

from industry.endpoints.blueprints.get_blueprints import (
    router as get_blueprints_router,
)
from industry.endpoints.blueprints.get_blueprints_copies import (
    router as get_blueprints_copies_router,
)

router = Router(tags=["Industry - Blueprints"])
router.add_router("", get_blueprints_router)
router.add_router("copies", get_blueprints_copies_router)

__all__ = ["router"]
