"""Tribe-group endpoints (list, create, detail, change, reports, hub)."""

from ninja import Router

from tribes.endpoints.groups import (
    get_tribe_group,
    get_tribe_groups,
    patch_tribe_group,
    post_tribe_group,
)
from tribes.endpoints.groups.get_tribe_group_about import (
    router as get_tribe_group_about_router,
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

# A GET and its write share a path, so they go on one Router (see events).
list_router = Router(tags=["Tribes - Groups"])
list_router.get(get_tribe_groups.PATH, **get_tribe_groups.ROUTE_SPEC)(
    get_tribe_groups.get_tribe_groups
)
list_router.post(post_tribe_group.PATH, **post_tribe_group.ROUTE_SPEC)(
    post_tribe_group.post_tribe_group
)
detail_router = Router(tags=["Tribes - Groups"])
detail_router.get(get_tribe_group.PATH, **get_tribe_group.ROUTE_SPEC)(
    get_tribe_group.get_tribe_group
)
detail_router.patch(patch_tribe_group.PATH, **patch_tribe_group.ROUTE_SPEC)(
    patch_tribe_group.patch_tribe_group
)

router = Router(tags=["Tribes - Groups"])
router.add_router("", list_router)
router.add_router("", detail_router)
router.add_router("", get_tribe_group_roster_router)
router.add_router("", get_tribe_group_growth_router)
router.add_router("", get_tribe_group_showcase_router)
router.add_router("", get_tribe_group_about_router)
router.add_router("", get_tribe_group_report_router)

__all__ = ["router"]
