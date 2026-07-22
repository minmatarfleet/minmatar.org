from ninja import Router

from market.endpoints.get_contracts import router as get_contracts_router
from market.endpoints.get_expectations_by_location import (
    router as get_expectations_by_location_router,
)
from market.endpoints.get_inferred_sales_volume import (
    router as get_inferred_sales_volume_router,
)
from market.endpoints.get_ops_monitor import router as get_ops_monitor_router
from market.endpoints.get_ops_monitor_history import (
    router as get_ops_monitor_history_router,
)
from market.endpoints.get_sell_orders import router as get_sell_orders_router

router = Router(tags=["Market"])
router.add_router("", get_contracts_router)
router.add_router("", get_expectations_by_location_router)
router.add_router("", get_sell_orders_router)
# Inferred sales before broader market routes that could shadow the path.
router.add_router("", get_inferred_sales_volume_router)
# History before live monitor so /ops-monitor/history is not shadowed.
router.add_router("", get_ops_monitor_history_router)
router.add_router("", get_ops_monitor_router)

__all__ = ["router"]
