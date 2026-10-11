"""Tribes API router — composed from per-resource sub-routers."""

from ninja import Router

from tribes.endpoints.external_guild import router as external_guild_router
from tribes.endpoints.groups import router as groups_router
from tribes.endpoints.memberships import router as memberships_router
from tribes.endpoints.tribes import router as tribes_router

router = Router(tags=["Tribes"])
# External-guild paths first so "/external-guild/..." is not captured as tribe_id.
router.add_router("", external_guild_router)
router.add_router("", tribes_router)
router.add_router("", groups_router)
router.add_router("", memberships_router)

__all__ = ["router"]
