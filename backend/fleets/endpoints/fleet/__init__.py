"""Per-fleet operations (detail, members, tracking, etc.)."""

from fleets.endpoints.fleet.delete_fleet import (
    PATH as delete_fleet_path,
    ROUTE_SPEC as delete_fleet_spec,
    delete_fleet as delete_fleet_by_id,
    METHOD as delete_fleet_method,
)
from fleets.endpoints.fleet.delete_fleet_role_volunteer import (
    PATH as delete_fleet_role_volunteer_path,
    ROUTE_SPEC as delete_fleet_role_volunteer_spec,
    delete_fleet_role_volunteer,
    METHOD as delete_fleet_role_volunteer_method,
)
from fleets.endpoints.fleet.get_fleet import (
    PATH as get_fleet_path,
    ROUTE_SPEC as get_fleet_spec,
    get_fleet,
    METHOD as get_fleet_method,
)
from fleets.endpoints.fleet.get_fleet_members import (
    PATH as get_fleet_members_path,
    ROUTE_SPEC as get_fleet_members_spec,
    get_fleet_members,
    METHOD as get_fleet_members_method,
)
from fleets.endpoints.fleet.get_fleet_role_volunteers import (
    PATH as get_fleet_role_volunteers_path,
    ROUTE_SPEC as get_fleet_role_volunteers_spec,
    get_fleet_role_volunteers,
    METHOD as get_fleet_role_volunteers_method,
)
from fleets.endpoints.fleet.get_fleet_users import (
    PATH as get_fleet_users_path,
    ROUTE_SPEC as get_fleet_users_spec,
    get_fleet_users,
    METHOD as get_fleet_users_method,
)
from fleets.endpoints.fleet.patch_fleet import (
    PATH as patch_fleet_path,
    ROUTE_SPEC as patch_fleet_spec,
    update_fleet,
    METHOD as patch_fleet_method,
)
from fleets.endpoints.fleet.post_fleet_pre_ping import (
    PATH as post_fleet_pre_ping_path,
    ROUTE_SPEC as post_fleet_pre_ping_spec,
    send_pre_ping,
    METHOD as post_fleet_pre_ping_method,
)
from fleets.endpoints.fleet.post_fleet_role_volunteer import (
    PATH as post_fleet_role_volunteer_path,
    ROUTE_SPEC as post_fleet_role_volunteer_spec,
    create_fleet_role_volunteer,
    METHOD as post_fleet_role_volunteer_method,
)
from fleets.endpoints.fleet.post_fleet_tracking import (
    PATH as post_fleet_tracking_path,
    ROUTE_SPEC as post_fleet_tracking_spec,
    start_fleet,
    METHOD as post_fleet_tracking_method,
)
from fleets.endpoints.fleet.post_refresh_fleet_motd import (
    PATH as post_refresh_fleet_motd_path,
    ROUTE_SPEC as post_refresh_fleet_motd_spec,
    refresh_fleet_motd,
    METHOD as post_refresh_fleet_motd_method,
)

_ROUTES = (
    (
        get_fleet_users_method,
        get_fleet_users_path,
        get_fleet_users_spec,
        get_fleet_users,
    ),
    (
        get_fleet_members_method,
        get_fleet_members_path,
        get_fleet_members_spec,
        get_fleet_members,
    ),
    (
        get_fleet_role_volunteers_method,
        get_fleet_role_volunteers_path,
        get_fleet_role_volunteers_spec,
        get_fleet_role_volunteers,
    ),
    (
        post_fleet_role_volunteer_method,
        post_fleet_role_volunteer_path,
        post_fleet_role_volunteer_spec,
        create_fleet_role_volunteer,
    ),
    (
        delete_fleet_role_volunteer_method,
        delete_fleet_role_volunteer_path,
        delete_fleet_role_volunteer_spec,
        delete_fleet_role_volunteer,
    ),
    (get_fleet_method, get_fleet_path, get_fleet_spec, get_fleet),
    (patch_fleet_method, patch_fleet_path, patch_fleet_spec, update_fleet),
    (
        post_fleet_tracking_method,
        post_fleet_tracking_path,
        post_fleet_tracking_spec,
        start_fleet,
    ),
    (
        delete_fleet_method,
        delete_fleet_path,
        delete_fleet_spec,
        delete_fleet_by_id,
    ),
    (
        post_refresh_fleet_motd_method,
        post_refresh_fleet_motd_path,
        post_refresh_fleet_motd_spec,
        refresh_fleet_motd,
    ),
    (
        post_fleet_pre_ping_method,
        post_fleet_pre_ping_path,
        post_fleet_pre_ping_spec,
        send_pre_ping,
    ),
)

__all__ = ["_ROUTES"]
