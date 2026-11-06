"""Freight settings editor."""

from ninja import Router

from freight.endpoints.manage.get_manage_routes import (
    METHOD as get_manage_routes_method,
    PATH as get_manage_routes_path,
    ROUTE_SPEC as get_manage_routes_spec,
    get_manage_routes,
)
from freight.endpoints.manage.post_manage_route import (
    METHOD as post_manage_route_method,
    PATH as post_manage_route_path,
    ROUTE_SPEC as post_manage_route_spec,
    post_manage_route,
)
from freight.endpoints.manage.patch_manage_route import (
    METHOD as patch_manage_route_method,
    PATH as patch_manage_route_path,
    ROUTE_SPEC as patch_manage_route_spec,
    patch_manage_route,
)

router = Router(tags=["Freight"])

_ROUTES = (
    (
        get_manage_routes_method,
        get_manage_routes_path,
        get_manage_routes_spec,
        get_manage_routes,
    ),
    (
        post_manage_route_method,
        post_manage_route_path,
        post_manage_route_spec,
        post_manage_route,
    ),
    (
        patch_manage_route_method,
        patch_manage_route_path,
        patch_manage_route_spec,
        patch_manage_route,
    ),
)
for method, path, spec, view in _ROUTES:
    getattr(router, method)(path, **spec)(view)

__all__ = ["router"]
