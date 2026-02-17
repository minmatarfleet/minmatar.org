"""Breakdown router: GET order breakdown and GET order item breakdown (mounted under orders)."""

from ninja import Router

from industry.endpoints.breakdown.get_order_breakdown import (
    PATH as get_order_breakdown_path,
    ROUTE_SPEC as get_order_breakdown_spec,
    get_order_breakdown,
    METHOD as get_order_breakdown_method,
)
from industry.endpoints.breakdown.get_order_item_breakdown import (
    PATH as get_order_item_breakdown_path,
    ROUTE_SPEC as get_order_item_breakdown_spec,
    get_order_item_breakdown,
    METHOD as get_order_item_breakdown_method,
)

router = Router(tags=["Industry - Breakdown"])

_ROUTES = (
    (
        get_order_breakdown_method,
        get_order_breakdown_path,
        get_order_breakdown_spec,
        get_order_breakdown,
    ),
    (
        get_order_item_breakdown_method,
        get_order_item_breakdown_path,
        get_order_item_breakdown_spec,
        get_order_item_breakdown,
    ),
)
for method, path, spec, view in _ROUTES:
    getattr(router, method)(path, **spec)(view)

__all__ = ["router"]
