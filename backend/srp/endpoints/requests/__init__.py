"""SRP reimbursement API v2 under /api/srp/v2/requests."""

from ninja import Router

from srp.endpoints.requests.get_request import (
    PATH as get_request_path,
    ROUTE_SPEC as get_request_spec,
    get_srp_request,
    METHOD as get_request_method,
)
from srp.endpoints.requests.get_requests_list import (
    PATH as list_path,
    ROUTE_SPEC as list_spec,
    list_srp_requests,
    METHOD as list_method,
)
from srp.endpoints.requests.patch_request import (
    PATH as patch_path,
    ROUTE_SPEC as patch_spec,
    patch_srp_request,
    METHOD as patch_method,
)
from srp.endpoints.requests.post_request import (
    PATH as post_path,
    ROUTE_SPEC as post_spec,
    create_srp_request,
    METHOD as post_method,
)

router = Router(tags=["SRP - Requests v2"])

_ROUTES = (
    (post_method, post_path, post_spec, create_srp_request),
    (list_method, list_path, list_spec, list_srp_requests),
    (get_request_method, get_request_path, get_request_spec, get_srp_request),
    (patch_method, patch_path, patch_spec, patch_srp_request),
)

for method, path, spec, view in _ROUTES:
    getattr(router, method)(path, **spec)(view)

__all__ = ["router"]
