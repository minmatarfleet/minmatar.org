from ninja import Router

from market.endpoints.get_character_statistics import (
    router as get_character_statistics_router,
)
from market.endpoints.get_contracts import router as get_contracts_router
from market.endpoints.get_contracts_metrics import (
    router as get_contracts_metrics_router,
)
from market.endpoints.get_expectations_by_location import (
    router as get_expectations_by_location_router,
)
from market.endpoints.get_inferred_sales_volume import (
    router as get_inferred_sales_volume_router,
)
from market.endpoints.get_market_health import (
    router as get_market_health_router,
)
from market.endpoints.get_sell_order_supply import (
    router as get_sell_order_supply_router,
)
from market.endpoints.get_sell_orders import router as get_sell_orders_router

router = Router(tags=["Market"])
router.add_router("", get_character_statistics_router)
# Metrics before /contracts so /contracts/metrics is not shadowed.
router.add_router("", get_contracts_metrics_router)
router.add_router("", get_contracts_router)
router.add_router("", get_expectations_by_location_router)
router.add_router("", get_sell_orders_router)
# Inferred sales before broader market routes that could shadow the path.
router.add_router("", get_inferred_sales_volume_router)
router.add_router("", get_sell_order_supply_router)
router.add_router("", get_market_health_router)

__all__ = ["router"]
