"""Tribe activity endpoints: per-activity metrics and leaderboard."""

from ninja import Router

from tribes.endpoints.activity.get_tribe_activity_leaderboard import (
    router as get_tribe_activity_leaderboard_router,
)
from tribes.endpoints.activity.get_tribe_activity_metrics import (
    router as get_tribe_activity_metrics_router,
)
from tribes.endpoints.activity.get_tribe_group_activity_definitions import (
    router as get_tribe_group_activity_definitions_router,
)

router = Router(tags=["Tribes - Activity"])
router.add_router("", get_tribe_activity_metrics_router)
router.add_router("", get_tribe_activity_leaderboard_router)
router.add_router("", get_tribe_group_activity_definitions_router)

__all__ = ["router"]
