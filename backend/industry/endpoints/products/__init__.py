"""Products router: list products, GET product by ID, breakdown, build and insights by ID."""

from ninja import Router

from industry.endpoints.products.get_product import (
    PATH as get_product_path,
    ROUTE_SPEC as get_product_spec,
    get_product,
    METHOD as get_product_method,
)
from industry.endpoints.products.get_product_build import (
    PATH as get_product_build_path,
    ROUTE_SPEC as get_product_build_spec,
    get_product_build,
    METHOD as get_product_build_method,
)
from industry.endpoints.products.get_product_breakdown import (
    PATH as get_product_breakdown_path,
    ROUTE_SPEC as get_product_breakdown_spec,
    get_product_breakdown,
    METHOD as get_product_breakdown_method,
)
from industry.endpoints.products.get_product_insights import (
    PATH as get_product_insights_path,
    ROUTE_SPEC as get_product_insights_spec,
    get_product_insights,
    METHOD as get_product_insights_method,
)
from industry.endpoints.products.get_products import (
    PATH as get_products_path,
    ROUTE_SPEC as get_products_spec,
    get_products,
    METHOD as get_products_method,
)

router = Router(tags=["Industry - Products"])

_ROUTES = (
    (get_products_method, get_products_path, get_products_spec, get_products),
    (
        get_product_breakdown_method,
        get_product_breakdown_path,
        get_product_breakdown_spec,
        get_product_breakdown,
    ),
    (
        get_product_build_method,
        get_product_build_path,
        get_product_build_spec,
        get_product_build,
    ),
    (
        get_product_insights_method,
        get_product_insights_path,
        get_product_insights_spec,
        get_product_insights,
    ),
    (get_product_method, get_product_path, get_product_spec, get_product),
)
for method, path, spec, view in _ROUTES:
    getattr(router, method)(path, **spec)(view)

__all__ = ["router"]
