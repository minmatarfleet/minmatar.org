"""Tribe-group endpoints (list, detail)."""

from ninja import Router

from tribes.endpoints.groups.get_tribe_groups import (
    router as get_tribe_groups_router,
)
from tribes.endpoints.groups.get_tribe_group import (
    router as get_tribe_group_router,
)

router = Router(tags=["Tribes - Groups"])
router.add_router("", get_tribe_groups_router)
router.add_router("", get_tribe_group_router)

__all__ = ["router"]
