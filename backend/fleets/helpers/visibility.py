"""Which fleets a list may show, now that tribe groups host fleets.

A fleet with no host group is unaffected. A group fleet is visible to
everyone when it is open to the alliance; otherwise only to the group's
active members, the people who manage the group and its FC. Alliance
metrics count only fleets anyone in the alliance could see.
See docs/tribes/tribe-publishing.md.
"""

from __future__ import annotations

from django.db.models import Q

from tribes.helpers.publishing import visible_group_ids


def alliance_fleets_q() -> Q:
    """Fleets that are not members-only group fleets."""
    return Q(host_group__isnull=True) | Q(open_to_alliance=True)


def visible_fleets_q(user) -> Q:
    """Filter for fleet lists shown to ``user``."""
    q = alliance_fleets_q()
    if not getattr(user, "is_authenticated", False) or not user.pk:
        return q
    if user.is_superuser:
        return Q()
    group_ids = visible_group_ids(user)
    if group_ids:
        q |= Q(host_group_id__in=group_ids)
    return q | Q(created_by_id=user.pk)
