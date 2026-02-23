from ninja import Router

from industry.endpoints.get_orders_breakdown_summary_flat import (
    router as get_orders_breakdown_summary_flat_router,
)
from industry.endpoints.get_orders_breakdown_summary_janice import (
    router as get_orders_breakdown_summary_janice_router,
)
from industry.endpoints.get_orders_breakdown_summary_nested import (
    router as get_orders_breakdown_summary_nested_router,
)
from industry.endpoints.get_orders_breakdown_summary_tsv import (
    router as get_orders_breakdown_summary_tsv_router,
)
from industry.endpoints.breakdown import router as breakdown_router
from industry.endpoints.get_types_type_id_breakdown import (
    router as get_types_type_id_breakdown_router,
)
from industry.endpoints.blueprints import router as blueprints_router
from industry.endpoints.orders import router as orders_router
from industry.endpoints.products import router as products_router

router = Router(tags=["Industry"])
router.add_router("blueprints", blueprints_router)
router.add_router("", get_types_type_id_breakdown_router)
router.add_router("orders", orders_router)
router.add_router("orders", breakdown_router)
router.add_router("products", products_router)
router.add_router(
    "summary",
    get_orders_breakdown_summary_nested_router,
)
router.add_router(
    "summary",
    get_orders_breakdown_summary_flat_router,
)
router.add_router(
    "summary",
    get_orders_breakdown_summary_janice_router,
)
router.add_router(
    "summary",
    get_orders_breakdown_summary_tsv_router,
)

__all__ = ["router"]
