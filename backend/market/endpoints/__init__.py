from ninja import Router

from market.endpoints.get_contracts import router as get_contracts_router
from market.endpoints.get_expectations_by_location import (
    router as get_expectations_by_location_router,
)
from market.endpoints.get_sell_orders import router as get_sell_orders_router

router = Router(tags=["Market"])
router.add_router("", get_contracts_router)
router.add_router("", get_expectations_by_location_router)
router.add_router("", get_sell_orders_router)

__all__ = ["router"]
