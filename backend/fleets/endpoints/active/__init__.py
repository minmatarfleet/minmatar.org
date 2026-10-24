"""Current in-game fleet and quick-start."""

from fleets.endpoints.active.current_fleets import (
    PATH as get_user_active_fleets_path,
    ROUTE_SPEC as get_user_active_fleets_spec,
    get_user_active_fleets,
    METHOD as get_user_active_fleets_method,
)
from fleets.endpoints.active.get_current_fleet_window import (
    PATH as get_current_fleet_window_path,
    ROUTE_SPEC as get_current_fleet_window_spec,
    get_current_fleet_window,
    METHOD as get_current_fleet_window_method,
)
from fleets.endpoints.active.get_my_fleets import (
    PATH as get_my_fleets_path,
    ROUTE_SPEC as get_my_fleets_spec,
    get_my_fleets,
    METHOD as get_my_fleets_method,
)
from fleets.endpoints.active.post_start_fleet_now import (
    PATH as post_start_fleet_now_path,
    ROUTE_SPEC as post_start_fleet_now_spec,
    start_fleet_now,
    METHOD as post_start_fleet_now_method,
)

_ROUTES = (
    (
        get_user_active_fleets_method,
        get_user_active_fleets_path,
        get_user_active_fleets_spec,
        get_user_active_fleets,
    ),
    (
        get_current_fleet_window_method,
        get_current_fleet_window_path,
        get_current_fleet_window_spec,
        get_current_fleet_window,
    ),
    (
        get_my_fleets_method,
        get_my_fleets_path,
        get_my_fleets_spec,
        get_my_fleets,
    ),
    (
        post_start_fleet_now_method,
        post_start_fleet_now_path,
        post_start_fleet_now_spec,
        start_fleet_now,
    ),
)

__all__ = ["_ROUTES"]
