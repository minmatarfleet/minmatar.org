"""Fleet list and create."""

from fleets.endpoints.catalog.get_v3_fleets import (
    PATH as get_v3_fleets_path,
    ROUTE_SPEC as get_v3_fleets_spec,
    get_v3_fleets,
    METHOD as get_v3_fleets_method,
)
from fleets.endpoints.catalog.get_my_fleet_fittings import (
    PATH as get_my_fleet_fittings_path,
    ROUTE_SPEC as get_my_fleet_fittings_spec,
    get_my_fleet_fittings,
    METHOD as get_my_fleet_fittings_method,
)
from fleets.endpoints.catalog.post_create_fleet import (
    PATH as post_create_fleet_path,
    ROUTE_SPEC as post_create_fleet_spec,
    create_fleet,
    METHOD as post_create_fleet_method,
)
from fleets.endpoints.catalog.post_ping_preview import (
    PATH as post_ping_preview_path,
    ROUTE_SPEC as post_ping_preview_spec,
    post_ping_preview,
    METHOD as post_ping_preview_method,
)

_ROUTES = (
    (
        get_my_fleet_fittings_method,
        get_my_fleet_fittings_path,
        get_my_fleet_fittings_spec,
        get_my_fleet_fittings,
    ),
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
    (
        post_ping_preview_method,
        post_ping_preview_path,
        post_ping_preview_spec,
        post_ping_preview,
    ),
)

__all__ = ["_ROUTES"]
