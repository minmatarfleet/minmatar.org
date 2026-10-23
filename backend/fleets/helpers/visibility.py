"""Which fleets a list may show, now that tribe groups host fleets.

A fleet with no host group is unaffected. A group fleet is visible to
everyone when it is open to the alliance; otherwise only to the group's
active members, the people who manage the group and its FC. Alliance
metrics count only fleets anyone in the alliance could see.
See docs/tribes/tribe-publishing.md.

A private (invite-only) fleet is left out of every list and count until it
is declassified, except for the people who may see it
(fleets.helpers.private_visibility).
"""

from __future__ import annotations

from django.db.models import Q

from fleets.helpers.private_visibility import (
    listed_private_q,
    private_hidden_q,
)
from tribes.helpers.publishing import visible_group_ids


def _is_strategic_fc(user) -> bool:
    """Strategic FCs see every fleet (fleets.endpoints.helpers)."""
    # Imported here: the feature registry imports fleet models.
    from groups.helpers.feature_access import (  # pylint: disable=import-outside-toplevel
        can_use_feature,
    )

    return can_use_feature(user, "fleets.manage_any")


def alliance_fleets_q() -> Q:
    """Fleets that are not members-only group fleets or private fleets."""
    return (Q(host_group__isnull=True) | Q(open_to_alliance=True)) & ~(
        private_hidden_q()
    )


def visible_fleets_q(user) -> Q:
    """Filter for fleet lists shown to ``user``."""
    q = alliance_fleets_q()
    if not getattr(user, "is_authenticated", False) or not user.pk:
        return q
    if user.is_superuser or _is_strategic_fc(user):
        return Q()
    group_ids = visible_group_ids(user)
    if group_ids:
        q |= Q(host_group_id__in=group_ids)
    q |= Q(created_by_id=user.pk)
    return q | (private_hidden_q() & listed_private_q(user))


def public_kills_allowed(fleet) -> bool:
    """Whether anyone with the link may see the fleet's kills page."""
    if fleet.status == "cancelled":
        return False
    if fleet.host_group_id and not fleet.open_to_alliance:
        return False
    if fleet.audience_id and fleet.audience.hidden:
        return False
    return True
