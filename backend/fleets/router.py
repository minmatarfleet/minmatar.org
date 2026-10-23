"""Compose the fleet HTTP API (single Router; nested add_router("", ...)
yields fleets/ + 301).

The routes are composed here rather than in ``fleets.endpoints.__init__`` so
that importing any ``fleets.endpoints`` module (helpers, schemas) does not
import every route module. Helpers such as ``fleets.helpers.npsi_actions``
import ``fleets.endpoints.helpers``, and the NPSI routes import those helpers
back, so an eager package init made that a circular import.
"""

import functools
import inspect
import typing

from django.http import Http404
from ninja import Router

from fleets.endpoints.active import _ROUTES as active_routes
from fleets.endpoints.catalog import _ROUTES as catalog_routes
from fleets.endpoints.fleet import _ROUTES as fleet_routes
from fleets.endpoints.metrics import _ROUTES as metrics_routes
from fleets.endpoints.npsi import _ROUTES as npsi_routes
from fleets.endpoints.private import _ROUTES as private_routes
from fleets.endpoints.reference import _ROUTES as reference_routes

router = Router(tags=["Fleets"])


def _hide_private_fleets(view_func):
    """A private fleet the caller can't see is a 404 on every fleet route,
    the same answer as a fleet that doesn't exist (a 403 would confirm it
    does). See docs/fleets/private-fleets.md."""

    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        fleet_id = kwargs.get("fleet_id")
        if fleet_id is not None:
            # pylint: disable=import-outside-toplevel
            from fleets.helpers.private_visibility import (
                private_fleet_hidden_from,
            )

            if private_fleet_hidden_from(request.user, fleet_id):
                raise Http404
        return view_func(request, *args, **kwargs)

    # Ninja reads the parameter types off the wrapper. String annotations
    # (``from __future__ import annotations``) must resolve in the view's
    # module, not this one, so hand it the resolved signature.
    hints = typing.get_type_hints(view_func)
    signature = inspect.signature(view_func)
    wrapper.__signature__ = signature.replace(
        parameters=[
            param.replace(annotation=hints.get(param.name, param.annotation))
            for param in signature.parameters.values()
        ],
        return_annotation=hints.get("return", signature.return_annotation),
    )
    return wrapper


for routes in (
    reference_routes,
    catalog_routes,
    npsi_routes,
    metrics_routes,
    active_routes,
    private_routes,
    fleet_routes,
):
    for method, path, spec, view in routes:
        getattr(router, method)(path, **spec)(_hide_private_fleets(view))

__all__ = ["router"]
