"""Tribes API router — composed from per-resource sub-routers."""

from ninja import Router

from tribes.endpoints.tribes import router as tribes_router
from tribes.endpoints.groups import router as groups_router
from tribes.endpoints.memberships import router as memberships_router
from tribes.endpoints.outreach import router as outreach_router

router = Router(tags=["Tribes"])
router.add_router("", tribes_router)
router.add_router("", groups_router)
router.add_router("", memberships_router)
router.add_router("", outreach_router)

__all__ = ["router"]
