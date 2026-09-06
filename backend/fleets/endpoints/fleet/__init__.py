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

from fleets.endpoints.fleet.patch_fleet_role_volunteer import (
    PATH as patch_fleet_role_volunteer_path,
    ROUTE_SPEC as patch_fleet_role_volunteer_spec,
    assign_fleet_role_volunteer_system,
    METHOD as patch_fleet_role_volunteer_method,
)
from fleets.endpoints.fleet.get_fleet_ship_volunteers import (
    PATH as get_fleet_ship_volunteers_path,
    ROUTE_SPEC as get_fleet_ship_volunteers_spec,
    get_fleet_ship_volunteers,
    METHOD as get_fleet_ship_volunteers_method,
)
from fleets.endpoints.fleet.delete_fleet_ship_volunteer import (
    PATH as delete_fleet_ship_volunteer_path,
    ROUTE_SPEC as delete_fleet_ship_volunteer_spec,
    delete_fleet_ship_volunteer,
    METHOD as delete_fleet_ship_volunteer_method,
)
from fleets.endpoints.fleet.get_fleet_refits import (
    PATH as get_fleet_refits_path,
    ROUTE_SPEC as get_fleet_refits_spec,
    get_fleet_refits,
    METHOD as get_fleet_refits_method,
)
from fleets.endpoints.fleet.post_fleet_refit import (
    PATH as post_fleet_refit_path,
    ROUTE_SPEC as post_fleet_refit_spec,
    create_fleet_refit,
    METHOD as post_fleet_refit_method,
)
from fleets.endpoints.fleet.delete_fleet_refit import (
    PATH as delete_fleet_refit_path,
    ROUTE_SPEC as delete_fleet_refit_spec,
    delete_fleet_refit,
    METHOD as delete_fleet_refit_method,
)

from fleets.endpoints.fleet.get_fleet_composition import (
    PATH as get_fleet_composition_path,
    ROUTE_SPEC as get_fleet_composition_spec,
    get_fleet_composition,
    METHOD as get_fleet_composition_method,
)
from fleets.endpoints.fleet.get_fleet_my_pilots import (
    PATH as get_fleet_my_pilots_path,
    ROUTE_SPEC as get_fleet_my_pilots_spec,
    get_fleet_my_pilots,
    METHOD as get_fleet_my_pilots_method,
)
from fleets.endpoints.fleet.put_fleet_my_ship_volunteers import (
    PATH as put_fleet_my_ship_volunteers_path,
    ROUTE_SPEC as put_fleet_my_ship_volunteers_spec,
    set_my_ship_volunteers,
    METHOD as put_fleet_my_ship_volunteers_method,
)
from fleets.endpoints.fleet.get_fleet_supply import (
    PATH as get_fleet_supply_path,
    ROUTE_SPEC as get_fleet_supply_spec,
    get_fleet_supply,
    METHOD as get_fleet_supply_method,
)
from fleets.endpoints.fleet.get_fleet_fitting_access import (
    PATH as get_fleet_fitting_access_path,
    ROUTE_SPEC as get_fleet_fitting_access_spec,
    get_fleet_fitting_access,
    METHOD as get_fleet_fitting_access_method,
)
from fleets.endpoints.fleet.post_fleet_fitting import (
    PATH as post_fleet_fitting_path,
    ROUTE_SPEC as post_fleet_fitting_spec,
    create_fleet_fitting,
    METHOD as post_fleet_fitting_method,
)
from fleets.endpoints.fleet.delete_fleet_fitting import (
    PATH as delete_fleet_fitting_path,
    ROUTE_SPEC as delete_fleet_fitting_spec,
    delete_fleet_fitting,
    METHOD as delete_fleet_fitting_method,
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
    (
        patch_fleet_role_volunteer_method,
        patch_fleet_role_volunteer_path,
        patch_fleet_role_volunteer_spec,
        assign_fleet_role_volunteer_system,
    ),
    (
        get_fleet_ship_volunteers_method,
        get_fleet_ship_volunteers_path,
        get_fleet_ship_volunteers_spec,
        get_fleet_ship_volunteers,
    ),
    (
        delete_fleet_ship_volunteer_method,
        delete_fleet_ship_volunteer_path,
        delete_fleet_ship_volunteer_spec,
        delete_fleet_ship_volunteer,
    ),
    (
        get_fleet_refits_method,
        get_fleet_refits_path,
        get_fleet_refits_spec,
        get_fleet_refits,
    ),
    (
        post_fleet_refit_method,
        post_fleet_refit_path,
        post_fleet_refit_spec,
        create_fleet_refit,
    ),
    (
        delete_fleet_refit_method,
        delete_fleet_refit_path,
        delete_fleet_refit_spec,
        delete_fleet_refit,
    ),
    (
        get_fleet_composition_method,
        get_fleet_composition_path,
        get_fleet_composition_spec,
        get_fleet_composition,
    ),
    (
        get_fleet_supply_method,
        get_fleet_supply_path,
        get_fleet_supply_spec,
        get_fleet_supply,
    ),
    (
        get_fleet_fitting_access_method,
        get_fleet_fitting_access_path,
        get_fleet_fitting_access_spec,
        get_fleet_fitting_access,
    ),
    (
        get_fleet_my_pilots_method,
        get_fleet_my_pilots_path,
        get_fleet_my_pilots_spec,
        get_fleet_my_pilots,
    ),
    (
        put_fleet_my_ship_volunteers_method,
        put_fleet_my_ship_volunteers_path,
        put_fleet_my_ship_volunteers_spec,
        set_my_ship_volunteers,
    ),
    (
        post_fleet_fitting_method,
        post_fleet_fitting_path,
        post_fleet_fitting_spec,
        create_fleet_fitting,
    ),
    (
        delete_fleet_fitting_method,
        delete_fleet_fitting_path,
        delete_fleet_fitting_spec,
        delete_fleet_fitting,
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
