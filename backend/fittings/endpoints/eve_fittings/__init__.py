"""EveFitting list/detail routes (mounted at /api/fittings/)."""

from ninja import Router

from fittings.endpoints.eve_fittings import (
    post_fitting_change_request,
    post_new_fitting_change_request,
)

from fittings.endpoints.eve_fittings.get_fitting import (
    PATH as get_fitting_path,
    ROUTE_SPEC as get_fitting_spec,
    get_fitting,
    METHOD as get_fitting_method,
)
from fittings.endpoints.eve_fittings.get_fittings import (
    PATH as get_fittings_path,
    ROUTE_SPEC as get_fittings_spec,
    get_fittings,
    METHOD as get_fittings_method,
)

router = Router(tags=["Ships"])

_ROUTES = (
    (
        post_new_fitting_change_request.METHOD,
        post_new_fitting_change_request.PATH,
        post_new_fitting_change_request.ROUTE_SPEC,
        post_new_fitting_change_request.post_new_fitting_change_request,
    ),
    (get_fittings_method, get_fittings_path, get_fittings_spec, get_fittings),
    (get_fitting_method, get_fitting_path, get_fitting_spec, get_fitting),
    (
        post_fitting_change_request.METHOD,
        post_fitting_change_request.PATH,
        post_fitting_change_request.ROUTE_SPEC,
        post_fitting_change_request.post_fitting_change_request,
    ),
)
for method, path, spec, view in _ROUTES:
    getattr(router, method)(path, **spec)(view)

__all__ = ["router"]
