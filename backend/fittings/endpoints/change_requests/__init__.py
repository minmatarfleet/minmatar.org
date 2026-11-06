"""Change-request review queue (mounted at /api/change-requests/)."""

from ninja import Router

from fittings.endpoints.change_requests import (
    get_change_requests,
    post_review_change_request,
)

router = Router(tags=["Ships"])

_ROUTES = (
    (
        get_change_requests.METHOD,
        get_change_requests.PATH,
        get_change_requests.ROUTE_SPEC,
        get_change_requests.get_change_requests,
    ),
    (
        post_review_change_request.METHOD,
        post_review_change_request.PATH,
        post_review_change_request.ROUTE_SPEC,
        post_review_change_request.post_review_change_request,
    ),
)
for method, path, spec, view in _ROUTES:
    getattr(router, method)(path, **spec)(view)

__all__ = ["router"]
