from ninja import Router

from buyback.endpoints.get_contracts import router as get_contracts_router
from buyback.endpoints.get_contracts_history import (
    router as get_contracts_history_router,
)
from buyback.endpoints.get_contracts_stats import (
    router as get_contracts_stats_router,
)
from buyback.endpoints.get_settings import router as get_settings_router
from buyback.endpoints.post_appraise import router as post_appraise_router

router = Router(tags=["Buyback"])
router.add_router("", get_settings_router)
router.add_router("", post_appraise_router)
router.add_router("", get_contracts_router)
router.add_router("contracts", get_contracts_history_router)
router.add_router("contracts", get_contracts_stats_router)

__all__ = ["router"]
