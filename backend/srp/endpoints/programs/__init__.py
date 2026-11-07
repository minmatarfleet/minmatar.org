"""SRP programs: list, amount history, edit amounts, recalculate."""

from ninja import Router

from srp.endpoints.programs import (
    get_program_history,
    get_programs,
    get_recalculation_preview,
    post_keep_filed_amounts,
    post_program,
    post_program_amount,
    post_recalculate_outstanding,
)

router = Router(tags=["SRP - Programs"])

_ROUTES = (
    (
        get_program_history.METHOD,
        get_program_history.PATH,
        get_program_history.ROUTE_SPEC,
        get_program_history.get_srp_program_history,
    ),
    (
        get_programs.METHOD,
        get_programs.PATH,
        get_programs.ROUTE_SPEC,
        get_programs.get_srp_programs,
    ),
    (
        post_program_amount.METHOD,
        post_program_amount.PATH,
        post_program_amount.ROUTE_SPEC,
        post_program_amount.post_program_amount,
    ),
    (
        get_recalculation_preview.METHOD,
        get_recalculation_preview.PATH,
        get_recalculation_preview.ROUTE_SPEC,
        get_recalculation_preview.get_recalculation_preview,
    ),
    (
        post_recalculate_outstanding.METHOD,
        post_recalculate_outstanding.PATH,
        post_recalculate_outstanding.ROUTE_SPEC,
        post_recalculate_outstanding.post_recalculate_outstanding,
    ),
    (
        post_keep_filed_amounts.METHOD,
        post_keep_filed_amounts.PATH,
        post_keep_filed_amounts.ROUTE_SPEC,
        post_keep_filed_amounts.post_keep_filed_amounts,
    ),
    (
        post_program.METHOD,
        post_program.PATH,
        post_program.ROUTE_SPEC,
        post_program.post_program,
    ),
)
for method, path, spec, view in _ROUTES:
    getattr(router, method)(path, **spec)(view)

__all__ = ["router"]
