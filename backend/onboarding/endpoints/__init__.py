from ninja import Router

from onboarding.endpoints.get_onboarding_status import (
    METHOD as get_status_method,
    PATH as get_status_path,
    ROUTE_SPEC as get_status_spec,
    get_onboarding_status,
)
from onboarding.endpoints.post_onboarding_ack import (
    METHOD as post_ack_method,
    PATH as post_ack_path,
    ROUTE_SPEC as post_ack_spec,
    post_onboarding_ack,
)

router = Router(tags=["Onboarding"])

# Register the more specific path before "{program_type}" so "srp/ack" is not one segment.
_ROUTES = (
    (post_ack_method, post_ack_path, post_ack_spec, post_onboarding_ack),
    (
        get_status_method,
        get_status_path,
        get_status_spec,
        get_onboarding_status,
    ),
)
for method, path, spec, view in _ROUTES:
    getattr(router, method)(path, **spec)(view)

__all__ = ["router"]
