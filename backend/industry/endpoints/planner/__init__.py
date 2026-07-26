"""Planner router: facilities, system industry, job plans."""

from ninja import Router

from industry.endpoints.planner.get_facilities import (
    METHOD as get_facilities_method,
    PATH as get_facilities_path,
    ROUTE_SPEC as get_facilities_spec,
    get_facilities,
)
from industry.endpoints.planner.get_facility import (
    METHOD as get_facility_method,
    PATH as get_facility_path,
    ROUTE_SPEC as get_facility_spec,
    get_facility,
)
from industry.endpoints.planner.get_system_industry import (
    METHOD as get_system_industry_method,
    PATH as get_system_industry_path,
    ROUTE_SPEC as get_system_industry_spec,
    get_system_industry,
)
from industry.endpoints.planner.post_plan import (
    METHOD as post_plan_method,
    PATH as post_plan_path,
    ROUTE_SPEC as post_plan_spec,
    post_plan,
)
from industry.endpoints.planner.post_refine_rate import (
    METHOD as post_refine_rate_method,
    PATH as post_refine_rate_path,
    ROUTE_SPEC as post_refine_rate_spec,
    post_refine_rate,
)

router = Router(tags=["Industry - Planner"])

_ROUTES = (
    (
        get_facilities_method,
        get_facilities_path,
        get_facilities_spec,
        get_facilities,
    ),
    (get_facility_method, get_facility_path, get_facility_spec, get_facility),
    (
        get_system_industry_method,
        get_system_industry_path,
        get_system_industry_spec,
        get_system_industry,
    ),
    (post_plan_method, post_plan_path, post_plan_spec, post_plan),
    (
        post_refine_rate_method,
        post_refine_rate_path,
        post_refine_rate_spec,
        post_refine_rate,
    ),
)
for method, path, spec, view in _ROUTES:
    getattr(router, method)(path, **spec)(view)

__all__ = ["router"]
