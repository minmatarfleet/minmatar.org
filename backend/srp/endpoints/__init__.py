from ninja import Router

from srp.endpoints.programs import router as programs_router
from srp.endpoints.reimbursements.get_fleet_srp import (
    PATH as get_fleet_srp_path,
    ROUTE_SPEC as get_fleet_srp_spec,
    get_fleet_srp,
    METHOD as get_fleet_srp_method,
)
from srp.endpoints.reimbursements.patch_fleet_srp import (
    PATH as patch_fleet_srp_path,
    ROUTE_SPEC as patch_fleet_srp_spec,
    update_fleet_srp,
    METHOD as patch_fleet_srp_method,
)
from srp.endpoints.reimbursements.post_fleet_srp import (
    PATH as post_fleet_srp_path,
    ROUTE_SPEC as post_fleet_srp_spec,
    create_fleet_srp,
    METHOD as post_fleet_srp_method,
)
from srp.endpoints.resolve.post_resolve_killmail import (
    PATH as post_resolve_killmail_path,
    ROUTE_SPEC as post_resolve_killmail_spec,
    resolve_killmail_for_srp,
    METHOD as post_resolve_killmail_method,
)
from srp.endpoints.stats import router as stats_router

router = Router(tags=["SRP"])

_REIMBURSEMENT_ROUTES = (
    (
        get_fleet_srp_method,
        get_fleet_srp_path,
        get_fleet_srp_spec,
        get_fleet_srp,
    ),
    (
        post_fleet_srp_method,
        post_fleet_srp_path,
        post_fleet_srp_spec,
        create_fleet_srp,
    ),
    (
        patch_fleet_srp_method,
        patch_fleet_srp_path,
        patch_fleet_srp_spec,
        update_fleet_srp,
    ),
)
for method, path, spec, view in _REIMBURSEMENT_ROUTES:
    getattr(router, method)(path, **spec)(view)

router.add_router("programs", programs_router)
router.add_router("stats", stats_router)

_ROOT_ROUTES = (
    (
        post_resolve_killmail_method,
        post_resolve_killmail_path,
        post_resolve_killmail_spec,
        resolve_killmail_for_srp,
    ),
)
for method, path, spec, view in _ROOT_ROUTES:
    getattr(router, method)(path, **spec)(view)

__all__ = ["router"]
