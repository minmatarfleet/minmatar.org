"""Fleet metrics endpoints."""

from fleets.endpoints.metrics.get_fleet_commander_metrics import (
    PATH as get_fleet_commander_metrics_path,
    ROUTE_SPEC as get_fleet_commander_metrics_spec,
    get_fleet_commander_metrics,
    METHOD as get_fleet_commander_metrics_method,
)
from fleets.endpoints.metrics.get_fleet_metrics import (
    PATH as get_fleet_metrics_path,
    ROUTE_SPEC as get_fleet_metrics_spec,
    get_fleet_metrics,
    METHOD as get_fleet_metrics_method,
)

_ROUTES = (
    (
        get_fleet_metrics_method,
        get_fleet_metrics_path,
        get_fleet_metrics_spec,
        get_fleet_metrics,
    ),
    (
        get_fleet_commander_metrics_method,
        get_fleet_commander_metrics_path,
        get_fleet_commander_metrics_spec,
        get_fleet_commander_metrics,
    ),
)

__all__ = ["_ROUTES"]
