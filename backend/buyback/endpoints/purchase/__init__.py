"""Buyback hangar purchase endpoints under /stock."""

from ninja import Router

from buyback.endpoints.purchase.get_capabilities import (
    PATH as get_capabilities_path,
    ROUTE_SPEC as get_capabilities_spec,
    get_capabilities,
    METHOD as get_capabilities_method,
)
from buyback.endpoints.purchase.get_orders import (
    PATH as get_orders_path,
    ROUTE_SPEC as get_orders_spec,
    get_orders,
    METHOD as get_orders_method,
)
from buyback.endpoints.purchase.post_fill import (
    PATH as post_fill_path,
    ROUTE_SPEC as post_fill_spec,
    post_fill,
    METHOD as post_fill_method,
)
from buyback.endpoints.purchase.post_order_cancel import (
    PATH as post_order_cancel_path,
    ROUTE_SPEC as post_order_cancel_spec,
    post_order_cancel,
    METHOD as post_order_cancel_method,
)
from buyback.endpoints.purchase.post_order_complete import (
    PATH as post_order_complete_path,
    ROUTE_SPEC as post_order_complete_spec,
    post_order_complete,
    METHOD as post_order_complete_method,
)
from buyback.endpoints.purchase.post_order_discord_ack import (
    PATH as post_order_discord_ack_path,
    ROUTE_SPEC as post_order_discord_ack_spec,
    post_order_discord_ack,
    METHOD as post_order_discord_ack_method,
)
from buyback.endpoints.purchase.post_orders import (
    PATH as post_orders_path,
    ROUTE_SPEC as post_orders_spec,
    post_orders,
    METHOD as post_orders_method,
)

router = Router(tags=["Buyback"])

_ROUTES = (
    (post_fill_method, post_fill_path, post_fill_spec, post_fill),
    (get_orders_method, get_orders_path, get_orders_spec, get_orders),
    (post_orders_method, post_orders_path, post_orders_spec, post_orders),
    (
        post_order_complete_method,
        post_order_complete_path,
        post_order_complete_spec,
        post_order_complete,
    ),
    (
        post_order_cancel_method,
        post_order_cancel_path,
        post_order_cancel_spec,
        post_order_cancel,
    ),
    (
        post_order_discord_ack_method,
        post_order_discord_ack_path,
        post_order_discord_ack_spec,
        post_order_discord_ack,
    ),
    (
        get_capabilities_method,
        get_capabilities_path,
        get_capabilities_spec,
        get_capabilities,
    ),
)
for method, path, spec, view in _ROUTES:
    getattr(router, method)(path, **spec)(view)

__all__ = ["router"]
