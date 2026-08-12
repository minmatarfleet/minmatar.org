"""Fitting buy orders router: list/create/detail/lines/swaps/jita/prices."""

from ninja import Router

from market.endpoints.fitting_buy_orders.delete_line import (
    PATH as delete_line_path,
    METHOD as delete_line_method,
    ROUTE_SPEC as delete_line_spec,
    delete_fitting_buy_line,
)
from market.endpoints.fitting_buy_orders.get_check_jita import (
    PATH as get_check_jita_path,
    METHOD as get_check_jita_method,
    ROUTE_SPEC as get_check_jita_spec,
    get_fitting_buy_check_jita,
)
from market.endpoints.fitting_buy_orders.get_order import (
    PATH as get_order_path,
    METHOD as get_order_method,
    ROUTE_SPEC as get_order_spec,
    get_fitting_buy_order,
)
from market.endpoints.fitting_buy_orders.get_orders import (
    PATH as get_orders_path,
    METHOD as get_orders_method,
    ROUTE_SPEC as get_orders_spec,
    get_fitting_buy_orders,
)
from market.endpoints.fitting_buy_orders.patch_order import (
    PATH as patch_order_path,
    METHOD as patch_order_method,
    ROUTE_SPEC as patch_order_spec,
    patch_fitting_buy_order,
)
from market.endpoints.fitting_buy_orders.post_check_jita import (
    PATH as post_check_jita_path,
    METHOD as post_check_jita_method,
    ROUTE_SPEC as post_check_jita_spec,
    post_fitting_buy_check_jita,
)
from market.endpoints.fitting_buy_orders.post_landed_prices import (
    PATH as post_landed_prices_path,
    METHOD as post_landed_prices_method,
    ROUTE_SPEC as post_landed_prices_spec,
    post_fitting_buy_landed_prices,
)
from market.endpoints.fitting_buy_orders.post_line import (
    PATH as post_line_path,
    METHOD as post_line_method,
    ROUTE_SPEC as post_line_spec,
    post_fitting_buy_line,
)
from market.endpoints.fitting_buy_orders.post_order import (
    PATH as post_order_path,
    METHOD as post_order_method,
    ROUTE_SPEC as post_order_spec,
    post_fitting_buy_order,
)
from market.endpoints.fitting_buy_orders.post_order_swap import (
    PATH as post_order_swap_path,
    METHOD as post_order_swap_method,
    ROUTE_SPEC as post_order_swap_spec,
    post_fitting_buy_order_swap,
)
from market.endpoints.fitting_buy_orders.post_swap import (
    PATH as post_swap_path,
    METHOD as post_swap_method,
    ROUTE_SPEC as post_swap_spec,
    post_fitting_buy_swap,
)
from market.endpoints.fitting_buy_orders.put_allocations import (
    PATH as put_allocations_path,
    METHOD as put_allocations_method,
    ROUTE_SPEC as put_allocations_spec,
    put_fitting_buy_allocations,
)

router = Router(tags=["Market"])

_ROUTES = (
    (
        get_orders_method,
        get_orders_path,
        get_orders_spec,
        get_fitting_buy_orders,
    ),
    (
        post_order_method,
        post_order_path,
        post_order_spec,
        post_fitting_buy_order,
    ),
    (get_order_method, get_order_path, get_order_spec, get_fitting_buy_order),
    (
        patch_order_method,
        patch_order_path,
        patch_order_spec,
        patch_fitting_buy_order,
    ),
    (post_line_method, post_line_path, post_line_spec, post_fitting_buy_line),
    (
        delete_line_method,
        delete_line_path,
        delete_line_spec,
        delete_fitting_buy_line,
    ),
    (post_swap_method, post_swap_path, post_swap_spec, post_fitting_buy_swap),
    (
        post_order_swap_method,
        post_order_swap_path,
        post_order_swap_spec,
        post_fitting_buy_order_swap,
    ),
    (
        put_allocations_method,
        put_allocations_path,
        put_allocations_spec,
        put_fitting_buy_allocations,
    ),
    (
        post_check_jita_method,
        post_check_jita_path,
        post_check_jita_spec,
        post_fitting_buy_check_jita,
    ),
    (
        get_check_jita_method,
        get_check_jita_path,
        get_check_jita_spec,
        get_fitting_buy_check_jita,
    ),
    (
        post_landed_prices_method,
        post_landed_prices_path,
        post_landed_prices_spec,
        post_fitting_buy_landed_prices,
    ),
)

for method, path, spec, view in _ROUTES:
    getattr(router, method)(path, **spec)(view)
