"""Recruitment candidate and outreach endpoints."""

from ninja import Router

from tribes.endpoints.outreach.get_candidates import (
    router as get_candidates_router,
)
from tribes.endpoints.outreach.post_outreach import (
    router as post_outreach_router,
)
from tribes.endpoints.outreach.get_outreach import (
    router as get_outreach_router,
)

router = Router(tags=["Tribes - Outreach"])
router.add_router("", get_candidates_router)
router.add_router("", post_outreach_router)
router.add_router("", get_outreach_router)

__all__ = ["router"]
