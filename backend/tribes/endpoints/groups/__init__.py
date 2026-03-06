"""Tribe-group endpoints (list, detail, activity)."""

from ninja import Router

from tribes.endpoints.groups.get_tribe_group import (
    router as get_tribe_group_router,
)
from tribes.endpoints.groups.get_tribe_group_activity import (
    router as get_tribe_group_activity_router,
)
from tribes.endpoints.groups.get_tribe_groups import (
    router as get_tribe_groups_router,
)

router = Router(tags=["Tribes - Groups"])
router.add_router("", get_tribe_groups_router)
router.add_router("", get_tribe_group_router)
router.add_router("", get_tribe_group_activity_router)

__all__ = ["router"]
