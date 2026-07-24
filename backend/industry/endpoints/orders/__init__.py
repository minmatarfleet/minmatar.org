"""Orders router: GET list/detail/orderitems, POST/PATCH assignments, POST/DELETE order."""

from ninja import Router

from industry.endpoints.orders.delete_order import (
    PATH as delete_order_path,
    ROUTE_SPEC as delete_order_spec,
    delete_order,
    METHOD as delete_order_method,
)
from industry.endpoints.orders.delete_order_blueprint_coordinator import (
    PATH as delete_order_blueprint_coordinator_path,
    ROUTE_SPEC as delete_order_blueprint_coordinator_spec,
    delete_order_blueprint_coordinator,
    METHOD as delete_order_blueprint_coordinator_method,
)
from industry.endpoints.orders.delete_order_mineral_coordinator import (
    PATH as delete_order_mineral_coordinator_path,
    ROUTE_SPEC as delete_order_mineral_coordinator_spec,
    delete_order_mineral_coordinator,
    METHOD as delete_order_mineral_coordinator_method,
)
from industry.endpoints.orders.delete_order_pi_coordinator import (
    PATH as delete_order_pi_coordinator_path,
    ROUTE_SPEC as delete_order_pi_coordinator_spec,
    delete_order_pi_coordinator,
    METHOD as delete_order_pi_coordinator_method,
)
from industry.endpoints.orders.get_order import (
    PATH as get_order_path,
    ROUTE_SPEC as get_order_spec,
    get_order,
    METHOD as get_order_method,
)
from industry.endpoints.orders.get_order_material_options import (
    PATH as get_order_material_options_path,
    ROUTE_SPEC as get_order_material_options_spec,
    get_order_material_options,
    METHOD as get_order_material_options_method,
)
from industry.endpoints.orders.get_orders import (
    PATH as get_orders_path,
    ROUTE_SPEC as get_orders_spec,
    get_orders,
    METHOD as get_orders_method,
)
from industry.endpoints.orders.get_orders_profit_summary import (
    PATH as get_orders_profit_summary_path,
    ROUTE_SPEC as get_orders_profit_summary_spec,
    get_orders_profit_summary,
    METHOD as get_orders_profit_summary_method,
)
from industry.endpoints.orders.get_order_orderitems import (
    PATH as get_order_orderitems_path,
    ROUTE_SPEC as get_order_orderitems_spec,
    get_order_orderitems,
    METHOD as get_order_orderitems_method,
)
from industry.endpoints.orders.patch_order_blueprint_coordinator import (
    PATH as patch_order_blueprint_coordinator_path,
    ROUTE_SPEC as patch_order_blueprint_coordinator_spec,
    patch_order_blueprint_coordinator,
    METHOD as patch_order_blueprint_coordinator_method,
)
from industry.endpoints.orders.patch_order_item_assignment import (
    PATH as patch_order_item_assignment_path,
    ROUTE_SPEC as patch_order_item_assignment_spec,
    patch_order_item_assignment,
    METHOD as patch_order_item_assignment_method,
)
from industry.endpoints.orders.patch_order_mineral_coordinator import (
    PATH as patch_order_mineral_coordinator_path,
    ROUTE_SPEC as patch_order_mineral_coordinator_spec,
    patch_order_mineral_coordinator,
    METHOD as patch_order_mineral_coordinator_method,
)
from industry.endpoints.orders.patch_order_pi_coordinator import (
    PATH as patch_order_pi_coordinator_path,
    ROUTE_SPEC as patch_order_pi_coordinator_spec,
    patch_order_pi_coordinator,
    METHOD as patch_order_pi_coordinator_method,
)
from industry.endpoints.orders.post_order import (
    PATH as post_order_path,
    ROUTE_SPEC as post_order_spec,
    post_order,
    METHOD as post_order_method,
)
from industry.endpoints.orders.post_order_blueprint_coordinator import (
    PATH as post_order_blueprint_coordinator_path,
    ROUTE_SPEC as post_order_blueprint_coordinator_spec,
    post_order_blueprint_coordinator,
    METHOD as post_order_blueprint_coordinator_method,
)
from industry.endpoints.orders.post_order_item_assignment import (
    PATH as post_order_item_assignment_path,
    ROUTE_SPEC as post_order_item_assignment_spec,
    post_order_item_assignment,
    METHOD as post_order_item_assignment_method,
)
from industry.endpoints.orders.post_order_mineral_coordinator import (
    PATH as post_order_mineral_coordinator_path,
    ROUTE_SPEC as post_order_mineral_coordinator_spec,
    post_order_mineral_coordinator,
    METHOD as post_order_mineral_coordinator_method,
)
from industry.endpoints.orders.post_order_pi_coordinator import (
    PATH as post_order_pi_coordinator_path,
    ROUTE_SPEC as post_order_pi_coordinator_spec,
    post_order_pi_coordinator,
    METHOD as post_order_pi_coordinator_method,
)
from industry.endpoints.orders.post_order_profit_breakdown_refresh import (
    PATH as post_order_profit_breakdown_refresh_path,
    ROUTE_SPEC as post_order_profit_breakdown_refresh_spec,
    post_order_profit_breakdown_refresh,
    METHOD as post_order_profit_breakdown_refresh_method,
)

router = Router(tags=["Industry - Orders"])

_ROUTES = (
    (get_orders_method, get_orders_path, get_orders_spec, get_orders),
    (
        get_orders_profit_summary_method,
        get_orders_profit_summary_path,
        get_orders_profit_summary_spec,
        get_orders_profit_summary,
    ),
    (post_order_method, post_order_path, post_order_spec, post_order),
    (get_order_method, get_order_path, get_order_spec, get_order),
    (
        get_order_material_options_method,
        get_order_material_options_path,
        get_order_material_options_spec,
        get_order_material_options,
    ),
    (delete_order_method, delete_order_path, delete_order_spec, delete_order),
    (
        post_order_profit_breakdown_refresh_method,
        post_order_profit_breakdown_refresh_path,
        post_order_profit_breakdown_refresh_spec,
        post_order_profit_breakdown_refresh,
    ),
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
    (
        post_order_blueprint_coordinator_method,
        post_order_blueprint_coordinator_path,
        post_order_blueprint_coordinator_spec,
        post_order_blueprint_coordinator,
    ),
    (
        patch_order_blueprint_coordinator_method,
        patch_order_blueprint_coordinator_path,
        patch_order_blueprint_coordinator_spec,
        patch_order_blueprint_coordinator,
    ),
    (
        delete_order_blueprint_coordinator_method,
        delete_order_blueprint_coordinator_path,
        delete_order_blueprint_coordinator_spec,
        delete_order_blueprint_coordinator,
    ),
    (
        post_order_mineral_coordinator_method,
        post_order_mineral_coordinator_path,
        post_order_mineral_coordinator_spec,
        post_order_mineral_coordinator,
    ),
    (
        patch_order_mineral_coordinator_method,
        patch_order_mineral_coordinator_path,
        patch_order_mineral_coordinator_spec,
        patch_order_mineral_coordinator,
    ),
    (
        delete_order_mineral_coordinator_method,
        delete_order_mineral_coordinator_path,
        delete_order_mineral_coordinator_spec,
        delete_order_mineral_coordinator,
    ),
    (
        post_order_pi_coordinator_method,
        post_order_pi_coordinator_path,
        post_order_pi_coordinator_spec,
        post_order_pi_coordinator,
    ),
    (
        patch_order_pi_coordinator_method,
        patch_order_pi_coordinator_path,
        patch_order_pi_coordinator_spec,
        patch_order_pi_coordinator,
    ),
    (
        delete_order_pi_coordinator_method,
        delete_order_pi_coordinator_path,
        delete_order_pi_coordinator_spec,
        delete_order_pi_coordinator,
    ),
)
for method, path, spec, view in _ROUTES:
    getattr(router, method)(path, **spec)(view)

__all__ = ["router"]
