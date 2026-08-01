"""Loyalty / LP buyback router."""

from ninja import Router

from industry.endpoints.loyalty.get_currencies import (
    PATH as get_currencies_path,
    ROUTE_SPEC as get_currencies_spec,
    get_currencies,
    METHOD as get_currencies_method,
)
from industry.endpoints.loyalty.get_ledger import (
    PATH as get_ledger_path,
    ROUTE_SPEC as get_ledger_spec,
    get_ledger,
    METHOD as get_ledger_method,
)
from industry.endpoints.loyalty.get_orders import (
    PATH as get_orders_path,
    ROUTE_SPEC as get_orders_spec,
    get_orders,
    METHOD as get_orders_method,
)
from industry.endpoints.loyalty.get_stockpiles import (
    PATH as get_stockpiles_path,
    ROUTE_SPEC as get_stockpiles_spec,
    get_stockpiles,
    METHOD as get_stockpiles_method,
)
from industry.endpoints.loyalty.patch_order import (
    PATH as patch_order_path,
    ROUTE_SPEC as patch_order_spec,
    patch_order,
    METHOD as patch_order_method,
)
from industry.endpoints.loyalty.post_order_claim import (
    PATH as post_order_claim_path,
    ROUTE_SPEC as post_order_claim_spec,
    post_order_claim,
    METHOD as post_order_claim_method,
)
from industry.endpoints.loyalty.post_orders import (
    PATH as post_orders_path,
    ROUTE_SPEC as post_orders_spec,
    post_orders,
    METHOD as post_orders_method,
)

router = Router(tags=["Industry - Loyalty"])

_ROUTES = (
    (
        get_currencies_method,
        get_currencies_path,
        get_currencies_spec,
        get_currencies,
    ),
    (
        get_stockpiles_method,
        get_stockpiles_path,
        get_stockpiles_spec,
        get_stockpiles,
    ),
    (get_ledger_method, get_ledger_path, get_ledger_spec, get_ledger),
    (get_orders_method, get_orders_path, get_orders_spec, get_orders),
    (post_orders_method, post_orders_path, post_orders_spec, post_orders),
    (
        post_order_claim_method,
        post_order_claim_path,
        post_order_claim_spec,
        post_order_claim,
    ),
    (patch_order_method, patch_order_path, patch_order_spec, patch_order),
)
for method, path, spec, view in _ROUTES:
    getattr(router, method)(path, **spec)(view)

__all__ = ["router"]
