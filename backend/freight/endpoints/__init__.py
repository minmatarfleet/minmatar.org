from ninja import Router

from freight.endpoints.get_contracts import router as get_contracts_router
from freight.endpoints.get_contracts_history import (
    router as get_contracts_history_router,
)
from freight.endpoints.get_character_statistics import (
    router as get_character_statistics_router,
)

router = Router(tags=["Freight"])
router.add_router("", get_contracts_router)
router.add_router("contracts", get_contracts_history_router)
router.add_router("", get_character_statistics_router)

__all__ = ["router"]
