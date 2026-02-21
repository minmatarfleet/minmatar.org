"""Orders router: public GET list, detail, orderitems, and breakdowns."""

from ninja import Router

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
from industry.endpoints.orders.get_order_orderitems import (
    PATH as get_order_orderitems_path,
    ROUTE_SPEC as get_order_orderitems_spec,
    get_order_orderitems,
    METHOD as get_order_orderitems_method,
)

router = Router(tags=["Industry - Orders"])

_ROUTES = (
    (get_orders_method, get_orders_path, get_orders_spec, get_orders),
    (get_order_method, get_order_path, get_order_spec, get_order),
    (
        get_order_orderitems_method,
        get_order_orderitems_path,
        get_order_orderitems_spec,
        get_order_orderitems,
    ),
)
for method, path, spec, view in _ROUTES:
    getattr(router, method)(path, **spec)(view)

__all__ = ["router"]
