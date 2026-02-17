"""Products router: list products, PUT product by type_id, GET product breakdown by ID."""

from ninja import Router

from industry.endpoints.products.get_product_breakdown import (
    PATH as get_product_breakdown_path,
    ROUTE_SPEC as get_product_breakdown_spec,
    get_product_breakdown,
    METHOD as get_product_breakdown_method,
)
from industry.endpoints.products.get_products import (
    PATH as get_products_path,
    ROUTE_SPEC as get_products_spec,
    get_products,
    METHOD as get_products_method,
)
from industry.endpoints.products.put_product import (
    PATH as put_product_path,
    ROUTE_SPEC as put_product_spec,
    put_product,
    METHOD as put_product_method,
)

router = Router(tags=["Industry - Products"])

_ROUTES = (
    (get_products_method, get_products_path, get_products_spec, get_products),
    (put_product_method, put_product_path, put_product_spec, put_product),
    (
        get_product_breakdown_method,
        get_product_breakdown_path,
        get_product_breakdown_spec,
        get_product_breakdown,
    ),
)
for method, path, spec, view in _ROUTES:
    getattr(router, method)(path, **spec)(view)

__all__ = ["router"]
