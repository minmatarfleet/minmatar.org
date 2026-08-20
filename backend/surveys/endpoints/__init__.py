"""Surveys API router — composed from member and management sub-routers."""

from ninja import Router

from surveys.endpoints.manage import router as manage_router
from surveys.endpoints.member import router as member_router

router = Router(tags=["Surveys"])
router.add_router("", member_router)
router.add_router("", manage_router)

__all__ = ["router"]
