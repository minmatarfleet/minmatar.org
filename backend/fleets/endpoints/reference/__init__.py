"""Reference data: types, locations, audiences."""

from fleets.endpoints.reference.get_fleet_audiences import (
    PATH as get_fleet_audiences_path,
    ROUTE_SPEC as get_fleet_audiences_spec,
    get_fleet_audiences,
    METHOD as get_fleet_audiences_method,
)
from fleets.endpoints.reference.get_fleet_types import (
    PATH as get_fleet_types_path,
    ROUTE_SPEC as get_fleet_types_spec,
    get_fleet_types,
    METHOD as get_fleet_types_method,
)
from fleets.endpoints.reference.get_v2_fleet_locations import (
    PATH as get_v2_fleet_locations_path,
    ROUTE_SPEC as get_v2_fleet_locations_spec,
    get_v2_fleet_locations,
    METHOD as get_v2_fleet_locations_method,
)

_ROUTES = (
    (
        get_fleet_types_method,
        get_fleet_types_path,
        get_fleet_types_spec,
        get_fleet_types,
    ),
    (
        get_v2_fleet_locations_method,
        get_v2_fleet_locations_path,
        get_v2_fleet_locations_spec,
        get_v2_fleet_locations,
    ),
    (
        get_fleet_audiences_method,
        get_fleet_audiences_path,
        get_fleet_audiences_spec,
        get_fleet_audiences,
    ),
)

__all__ = ["_ROUTES"]
