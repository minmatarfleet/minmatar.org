"""Tribe-group endpoints (list, detail, reports, hub)."""

from ninja import Router

from tribes.endpoints.groups.get_tribe_group import (
    router as get_tribe_group_router,
)
from tribes.endpoints.groups.get_tribe_group_growth import (
    router as get_tribe_group_growth_router,
)
from tribes.endpoints.groups.get_tribe_group_report import (
    router as get_tribe_group_report_router,
)
from tribes.endpoints.groups.get_tribe_group_roster import (
    router as get_tribe_group_roster_router,
)
from tribes.endpoints.groups.get_tribe_group_showcase import (
    router as get_tribe_group_showcase_router,
)
from tribes.endpoints.groups.get_tribe_groups import (
    router as get_tribe_groups_router,
)

router = Router(tags=["Tribes - Groups"])
router.add_router("", get_tribe_groups_router)
router.add_router("", get_tribe_group_router)
router.add_router("", get_tribe_group_roster_router)
router.add_router("", get_tribe_group_growth_router)
router.add_router("", get_tribe_group_showcase_router)
router.add_router("", get_tribe_group_report_router)

__all__ = ["router"]
