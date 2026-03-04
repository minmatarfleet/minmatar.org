"""Recruitment candidate endpoints."""

from ninja import Router

from tribes.endpoints.outreach.get_candidates import (
    router as get_candidates_router,
)

router = Router(tags=["Tribes - Outreach"])
router.add_router("", get_candidates_router)

__all__ = ["router"]
