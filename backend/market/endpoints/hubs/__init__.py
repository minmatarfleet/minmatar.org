"""Market hub and stocking-expectation editor (market.manage)."""

from ninja import Router

from market.endpoints.hubs.add_hub import (
    METHOD as add_hub_method,
    PATH as add_hub_path,
    ROUTE_SPEC as add_hub_spec,
    add_hub,
)
from market.endpoints.hubs.delete_item_expectation import (
    METHOD as delete_item_expectation_method,
    PATH as delete_item_expectation_path,
    ROUTE_SPEC as delete_item_expectation_spec,
    delete_item_expectation,
)
from market.endpoints.hubs.get_hub_expectations import (
    METHOD as get_hub_expectations_method,
    PATH as get_hub_expectations_path,
    ROUTE_SPEC as get_hub_expectations_spec,
    get_hub_expectations,
)
from market.endpoints.hubs.list_hubs import (
    METHOD as list_hubs_method,
    PATH as list_hubs_path,
    ROUTE_SPEC as list_hubs_spec,
    list_hubs,
)
from market.endpoints.hubs.patch_hub import (
    METHOD as patch_hub_method,
    PATH as patch_hub_path,
    ROUTE_SPEC as patch_hub_spec,
    patch_hub,
)
from market.endpoints.hubs.post_from_doctrine import (
    METHOD as post_from_doctrine_method,
    PATH as post_from_doctrine_path,
    ROUTE_SPEC as post_from_doctrine_spec,
    post_from_doctrine,
)
from market.endpoints.hubs.post_item_expectation import (
    METHOD as post_item_expectation_method,
    PATH as post_item_expectation_path,
    ROUTE_SPEC as post_item_expectation_spec,
    post_item_expectation,
)
from market.endpoints.hubs.put_contract_expectation import (
    METHOD as put_contract_expectation_method,
    PATH as put_contract_expectation_path,
    ROUTE_SPEC as put_contract_expectation_spec,
    put_contract_expectation,
)
from market.endpoints.hubs.put_fitting_expectation import (
    METHOD as put_fitting_expectation_method,
    PATH as put_fitting_expectation_path,
    ROUTE_SPEC as put_fitting_expectation_spec,
    put_fitting_expectation,
)
from market.endpoints.hubs.remove_hub import (
    METHOD as remove_hub_method,
    PATH as remove_hub_path,
    ROUTE_SPEC as remove_hub_spec,
    remove_hub,
)
from market.endpoints.hubs.type_search import (
    METHOD as type_search_method,
    PATH as type_search_path,
    ROUTE_SPEC as type_search_spec,
    type_search,
)

router = Router(tags=["Market"])

_ROUTES = (
    (add_hub_method, add_hub_path, add_hub_spec, add_hub),
    (
        delete_item_expectation_method,
        delete_item_expectation_path,
        delete_item_expectation_spec,
        delete_item_expectation,
    ),
    (
        get_hub_expectations_method,
        get_hub_expectations_path,
        get_hub_expectations_spec,
        get_hub_expectations,
    ),
    (list_hubs_method, list_hubs_path, list_hubs_spec, list_hubs),
    (patch_hub_method, patch_hub_path, patch_hub_spec, patch_hub),
    (
        post_from_doctrine_method,
        post_from_doctrine_path,
        post_from_doctrine_spec,
        post_from_doctrine,
    ),
    (
        post_item_expectation_method,
        post_item_expectation_path,
        post_item_expectation_spec,
        post_item_expectation,
    ),
    (
        put_contract_expectation_method,
        put_contract_expectation_path,
        put_contract_expectation_spec,
        put_contract_expectation,
    ),
    (
        put_fitting_expectation_method,
        put_fitting_expectation_path,
        put_fitting_expectation_spec,
        put_fitting_expectation,
    ),
    (remove_hub_method, remove_hub_path, remove_hub_spec, remove_hub),
    (type_search_method, type_search_path, type_search_spec, type_search),
)
for method, path, spec, view in _ROUTES:
    getattr(router, method)(path, **spec)(view)

__all__ = ["router"]
