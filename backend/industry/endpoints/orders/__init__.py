"""One router for orders. Every endpoint registered directly (same pattern as characters)."""

from ninja import Router

from industry.endpoints.orders.delete_order import (
    PATH as delete_order_path,
    ROUTE_SPEC as delete_order_spec,
    delete_order,
    METHOD as delete_order_method,
)
from industry.endpoints.orders.get_order import (
    PATH as get_order_path,
    ROUTE_SPEC as get_order_spec,
    get_order,
    METHOD as get_order_method,
)
from industry.endpoints.orders.get_orders import (
    PATH as get_orders_path,
    ROUTE_SPEC as get_orders_spec,
    get_orders,
    METHOD as get_orders_method,
)
from industry.endpoints.orders.post_order import (
    PATH as post_order_path,
    ROUTE_SPEC as post_order_spec,
    post_order,
    METHOD as post_order_method,
)

router = Router(tags=["Industry - Orders"])

_ROUTES = (
    (get_orders_method, get_orders_path, get_orders_spec, get_orders),
    (get_order_method, get_order_path, get_order_spec, get_order),
    (post_order_method, post_order_path, post_order_spec, post_order),
    (delete_order_method, delete_order_path, delete_order_spec, delete_order),
)
for method, path, spec, view in _ROUTES:
    getattr(router, method)(path, **spec)(view)

__all__ = ["router"]
