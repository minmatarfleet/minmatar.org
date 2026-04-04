"""Doctrine routes (mounted at /api/doctrines/)."""

from ninja import Router

from fittings.endpoints.doctrines.get_doctrine import (
    PATH as get_doctrine_path,
    ROUTE_SPEC as get_doctrine_spec,
    get_doctrine,
    METHOD as get_doctrine_method,
)
from fittings.endpoints.doctrines.get_doctrines import (
    PATH as get_doctrines_path,
    ROUTE_SPEC as get_doctrines_spec,
    get_doctrines,
    METHOD as get_doctrines_method,
)
from fittings.endpoints.doctrines.get_market_locations_with_doctrines import (
    PATH as get_market_locations_path,
    ROUTE_SPEC as get_market_locations_spec,
    get_market_locations_with_doctrines,
    METHOD as get_market_locations_method,
)

router = Router(tags=["Ships"])

_ROUTES = (
    (
        get_doctrines_method,
        get_doctrines_path,
        get_doctrines_spec,
        get_doctrines,
    ),
    (
        get_market_locations_method,
        get_market_locations_path,
        get_market_locations_spec,
        get_market_locations_with_doctrines,
    ),
    (get_doctrine_method, get_doctrine_path, get_doctrine_spec, get_doctrine),
)
for method, path, spec, view in _ROUTES:
    getattr(router, method)(path, **spec)(view)

__all__ = ["router"]
