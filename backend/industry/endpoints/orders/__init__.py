"""Orders router: GET list/detail/orderitems, POST/PATCH assignments, POST/DELETE order."""

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
from industry.endpoints.orders.get_order_orderitems import (
    PATH as get_order_orderitems_path,
    ROUTE_SPEC as get_order_orderitems_spec,
    get_order_orderitems,
    METHOD as get_order_orderitems_method,
)
from industry.endpoints.orders.patch_order_item_assignment import (
    PATH as patch_order_item_assignment_path,
    ROUTE_SPEC as patch_order_item_assignment_spec,
    patch_order_item_assignment,
    METHOD as patch_order_item_assignment_method,
)
from industry.endpoints.orders.post_order import (
    PATH as post_order_path,
    ROUTE_SPEC as post_order_spec,
    post_order,
    METHOD as post_order_method,
)
from industry.endpoints.orders.post_order_item_assignment import (
    PATH as post_order_item_assignment_path,
    ROUTE_SPEC as post_order_item_assignment_spec,
    post_order_item_assignment,
    METHOD as post_order_item_assignment_method,
)

router = Router(tags=["Industry - Orders"])

_ROUTES = (
    (get_orders_method, get_orders_path, get_orders_spec, get_orders),
    (post_order_method, post_order_path, post_order_spec, post_order),
    (get_order_method, get_order_path, get_order_spec, get_order),
    (delete_order_method, delete_order_path, delete_order_spec, delete_order),
    (
        get_order_orderitems_method,
        get_order_orderitems_path,
        get_order_orderitems_spec,
        get_order_orderitems,
    ),
    (
        post_order_item_assignment_method,
        post_order_item_assignment_path,
        post_order_item_assignment_spec,
        post_order_item_assignment,
    ),
    (
        patch_order_item_assignment_method,
        patch_order_item_assignment_path,
        patch_order_item_assignment_spec,
        patch_order_item_assignment,
    ),
)
for method, path, spec, view in _ROUTES:
    getattr(router, method)(path, **spec)(view)

__all__ = ["router"]
