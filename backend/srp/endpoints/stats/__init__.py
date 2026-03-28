"""SRP statistics: GET /srp/stats/overview and GET /srp/stats/history."""

from ninja import Router

from srp.endpoints.stats.get_stats_history import (
    PATH as get_stats_history_path,
    ROUTE_SPEC as get_stats_history_spec,
    get_srp_stats_history,
    METHOD as get_stats_history_method,
)
from srp.endpoints.stats.get_stats_overview import (
    PATH as get_stats_overview_path,
    ROUTE_SPEC as get_stats_overview_spec,
    get_srp_stats_overview,
    METHOD as get_stats_overview_method,
)

router = Router(tags=["SRP - Stats"])

_ROUTES = (
    (
        get_stats_overview_method,
        get_stats_overview_path,
        get_stats_overview_spec,
        get_srp_stats_overview,
    ),
    (
        get_stats_history_method,
        get_stats_history_path,
        get_stats_history_spec,
        get_srp_stats_history,
    ),
)
for method, path, spec, view in _ROUTES:
    getattr(router, method)(path, **spec)(view)

__all__ = ["router"]
