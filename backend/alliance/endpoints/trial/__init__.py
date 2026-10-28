from ninja import Router

from alliance.endpoints.trial.get_my_trial import router as get_my_trial_router
from alliance.endpoints.trial.get_my_trial_status import (
    router as get_my_trial_status_router,
)

router = Router(tags=["Alliance"])
router.add_router("", get_my_trial_status_router)
router.add_router("", get_my_trial_router)

__all__ = ["router"]
