"""Tribe-level members endpoints (e.g. member activity)."""

from ninja import Router

from tribes.endpoints.members.get_tribe_member_activity import (
    router as get_tribe_member_activity_router,
)

router = Router(tags=["Tribes - Members"])
router.add_router("", get_tribe_member_activity_router)

__all__ = ["router"]
