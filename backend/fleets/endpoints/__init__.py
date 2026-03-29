"""Compose fleet HTTP API (single Router — nested add_router(\"\", ...) yields fleets/ + 301)."""

from ninja import Router

from fleets.endpoints.active import _ROUTES as active_routes
from fleets.endpoints.catalog import _ROUTES as catalog_routes
from fleets.endpoints.fleet import _ROUTES as fleet_routes
from fleets.endpoints.metrics import _ROUTES as metrics_routes
from fleets.endpoints.reference import _ROUTES as reference_routes

router = Router(tags=["Fleets"])

for routes in (
    reference_routes,
    catalog_routes,
    metrics_routes,
    active_routes,
    fleet_routes,
):
    for method, path, spec, view in routes:
        getattr(router, method)(path, **spec)(view)

__all__ = ["router"]
