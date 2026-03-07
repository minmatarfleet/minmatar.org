"""Mining systems router: GET systems list, POST completion."""

from ninja import Router

from industry.endpoints.mining.get_systems import (
    PATH as get_systems_path,
    ROUTE_SPEC as get_systems_spec,
    get_systems,
    METHOD as get_systems_method,
)
from industry.endpoints.mining.post_completion import (
    PATH as post_completion_path,
    ROUTE_SPEC as post_completion_spec,
    post_completion,
    METHOD as post_completion_method,
)

router = Router(tags=["Industry - Mining"])

_ROUTES = (
    (get_systems_method, get_systems_path, get_systems_spec, get_systems),
    (
        post_completion_method,
        post_completion_path,
        post_completion_spec,
        post_completion,
    ),
)
for method, path, spec, view in _ROUTES:
    getattr(router, method)(path, **spec)(view)

__all__ = ["router"]
