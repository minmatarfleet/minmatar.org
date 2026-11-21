"""Who may load the fleet form's reference data (types, form-up locations).

Alliance fleets need fleets.create. A pilot who may schedule fleets for a
tribe group (its fleet policy) hosts group fleets without fleets.create, as
POST /api/fleets already allows, so they get the reference data too.
See docs/tribes/group-fleet-scheduling-analysis.md.
"""

from __future__ import annotations

from groups.helpers.feature_access import can_use_feature, require_feature
from tribes.helpers.publishing import KIND_FLEET, publishable_groups


def can_create_alliance_fleets(user) -> bool:
    return can_use_feature(user, "fleets.create")


def can_host_group_fleets(user) -> bool:
    """True if the user may schedule fleets for at least one tribe group."""
    return bool(publishable_groups(user, KIND_FLEET))


def fleet_form_denied(user) -> tuple[int, dict] | None:
    """None if the user may load the fleet form, else the 403."""
    if can_create_alliance_fleets(user) or can_host_group_fleets(user):
        return None
    return require_feature(user, "fleets.create")
