from ninja import Router

from alliance.endpoints.health.get_attention import (
    METHOD as get_attention_method,
    PATH as get_attention_path,
    ROUTE_SPEC as get_attention_spec,
    get_health_attention,
)
from alliance.endpoints.health.get_cohorts import (
    METHOD as get_cohorts_method,
    PATH as get_cohorts_path,
    ROUTE_SPEC as get_cohorts_spec,
    get_health_cohorts,
)
from alliance.endpoints.health.get_corporations import (
    METHOD as get_corporations_method,
    PATH as get_corporations_path,
    ROUTE_SPEC as get_corporations_spec,
    get_health_corporations,
)
from alliance.endpoints.health.get_overview import (
    METHOD as get_overview_method,
    PATH as get_overview_path,
    ROUTE_SPEC as get_overview_spec,
    get_health_overview,
)

router = Router(tags=["Alliance - Health"])

_ROUTES = (
    (
        get_overview_method,
        get_overview_path,
        get_overview_spec,
        get_health_overview,
    ),
    (
        get_attention_method,
        get_attention_path,
        get_attention_spec,
        get_health_attention,
    ),
    (
        get_corporations_method,
        get_corporations_path,
        get_corporations_spec,
        get_health_corporations,
    ),
    (
        get_cohorts_method,
        get_cohorts_path,
        get_cohorts_spec,
        get_health_cohorts,
    ),
)
for method, path, spec, view in _ROUTES:
    getattr(router, method)(path, **spec)(view)

__all__ = ["router"]
