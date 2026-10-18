"""Tribe publishing endpoints: settings, pickers and events."""

from ninja import Router

from tribes.endpoints.publishing.get_discord_channels import (
    router as get_discord_channels_router,
)
from tribes.endpoints.publishing.get_group_publishing import (
    PATH as PUBLISHING_PATH,
    ROUTE_SPEC as GET_PUBLISHING_SPEC,
    get_group_publishing,
)
from tribes.endpoints.publishing.get_publishable_groups import (
    router as get_publishable_groups_router,
)
from tribes.endpoints.publishing.patch_group_publishing import (
    ROUTE_SPEC as PATCH_PUBLISHING_SPEC,
    patch_group_publishing,
)

router = Router(tags=["Tribes - Publishing"])
router.add_router("", get_publishable_groups_router)
router.add_router("", get_discord_channels_router)
# GET and PATCH share a path, so they go on one Router (see memberships).
router.get(PUBLISHING_PATH, **GET_PUBLISHING_SPEC)(get_group_publishing)
router.patch(PUBLISHING_PATH, **PATCH_PUBLISHING_SPEC)(patch_group_publishing)

__all__ = ["router"]
