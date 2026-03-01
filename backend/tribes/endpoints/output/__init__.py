"""Output, leaderboard, and manual activity endpoints."""

from ninja import Router

from tribes.endpoints.output.get_output import router as get_output_router
from tribes.endpoints.output.get_tribe_output import (
    router as get_tribe_output_router,
)
from tribes.endpoints.output.get_group_output import (
    router as get_group_output_router,
)
from tribes.endpoints.output.get_group_leaderboard import (
    router as get_group_leaderboard_router,
)
from tribes.endpoints.output.post_activity import (
    router as post_activity_router,
)

router = Router(tags=["Tribes - Output"])
router.add_router("", get_output_router)
router.add_router("", get_tribe_output_router)
router.add_router("", get_group_output_router)
router.add_router("", get_group_leaderboard_router)
router.add_router("", post_activity_router)

__all__ = ["router"]
