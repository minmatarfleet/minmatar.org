"""SRP programs: GET list and GET amount history under /srp/programs."""

from ninja import Router

from srp.endpoints.programs.get_program_history import (
    PATH as get_program_history_path,
    ROUTE_SPEC as get_program_history_spec,
    get_srp_program_history,
    METHOD as get_program_history_method,
)
from srp.endpoints.programs.get_programs import (
    PATH as get_programs_path,
    ROUTE_SPEC as get_programs_spec,
    get_srp_programs,
    METHOD as get_programs_method,
)

router = Router(tags=["SRP - Programs"])

_ROUTES = (
    (
        get_program_history_method,
        get_program_history_path,
        get_program_history_spec,
        get_srp_program_history,
    ),
    (
        get_programs_method,
        get_programs_path,
        get_programs_spec,
        get_srp_programs,
    ),
)
for method, path, spec, view in _ROUTES:
    getattr(router, method)(path, **spec)(view)

__all__ = ["router"]
