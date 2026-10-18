"""Compose the fleet HTTP API (single Router; nested add_router("", ...)
yields fleets/ + 301).

The routes are composed here rather than in ``fleets.endpoints.__init__`` so
that importing any ``fleets.endpoints`` module (helpers, schemas) does not
import every route module. Helpers such as ``fleets.helpers.npsi_actions``
import ``fleets.endpoints.helpers``, and the NPSI routes import those helpers
back, so an eager package init made that a circular import.
"""

from ninja import Router

from fleets.endpoints.active import _ROUTES as active_routes
from fleets.endpoints.catalog import _ROUTES as catalog_routes
from fleets.endpoints.fleet import _ROUTES as fleet_routes
from fleets.endpoints.metrics import _ROUTES as metrics_routes
from fleets.endpoints.npsi import _ROUTES as npsi_routes
from fleets.endpoints.reference import _ROUTES as reference_routes

router = Router(tags=["Fleets"])

for routes in (
    reference_routes,
    catalog_routes,
    npsi_routes,
    metrics_routes,
    active_routes,
    fleet_routes,
):
    for method, path, spec, view in routes:
        getattr(router, method)(path, **spec)(view)

__all__ = ["router"]
