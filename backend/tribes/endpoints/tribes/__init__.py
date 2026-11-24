"""Tribe-level endpoints (list, create, current, detail, change)."""

from ninja import Router

from tribes.endpoints.tribes import (
    get_tribe,
    get_tribes,
    patch_tribe,
    post_tribe,
)
from tribes.endpoints.tribes.get_current_tribes import (
    router as get_current_tribes_router,
)
from tribes.endpoints.tribes.get_tribe_about import (
    router as get_tribe_about_router,
)

# A GET and its write share a path, so they go on one Router (see events).
list_router = Router(tags=["Tribes"])
list_router.get(get_tribes.PATH, **get_tribes.ROUTE_SPEC)(
    get_tribes.get_tribes
)
list_router.post(post_tribe.PATH, **post_tribe.ROUTE_SPEC)(
    post_tribe.post_tribe
)
detail_router = Router(tags=["Tribes"])
detail_router.get(get_tribe.PATH, **get_tribe.ROUTE_SPEC)(get_tribe.get_tribe)
detail_router.patch(patch_tribe.PATH, **patch_tribe.ROUTE_SPEC)(
    patch_tribe.patch_tribe
)

router = Router(tags=["Tribes"])
router.add_router("", list_router)
# "/current" before "/{tribe_id}".
router.add_router("", get_current_tribes_router)
router.add_router("", detail_router)
router.add_router("", get_tribe_about_router)

__all__ = ["router"]
