"""Fleet list and create."""

from fleets.endpoints.catalog.get_v3_fleets import (
    PATH as get_v3_fleets_path,
    ROUTE_SPEC as get_v3_fleets_spec,
    get_v3_fleets,
    METHOD as get_v3_fleets_method,
)
from fleets.endpoints.catalog.post_create_fleet import (
    PATH as post_create_fleet_path,
    ROUTE_SPEC as post_create_fleet_spec,
    create_fleet,
    METHOD as post_create_fleet_method,
)

_ROUTES = (
    (
        get_v3_fleets_method,
        get_v3_fleets_path,
        get_v3_fleets_spec,
        get_v3_fleets,
    ),
    (
        post_create_fleet_method,
        post_create_fleet_path,
        post_create_fleet_spec,
        create_fleet,
    ),
)

__all__ = ["_ROUTES"]
