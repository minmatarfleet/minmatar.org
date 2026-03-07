"""Sovereignty helpers for admin and elsewhere."""

from eveuniverse.models import EveType

# Group ID for the Sovereignty Hub structure itself (exclude from upgrade picklist).
SOVEREIGNTY_HUB_GROUP_ID = 1012


def get_sovereignty_upgrade_types_queryset():
    """
    Return EveTypes that are sovereignty upgrades (installable in the Sovereignty Hub).
    E.g. Advanced Logistics Network, Cynosural Navigation, Prospecting Arrays, etc.
    Excludes the Sovereignty Hub structure (group 1012).
    """
    return (
        EveType.objects.filter(eve_group__name__icontains="Sovereignty Hub")
        .exclude(eve_group_id=SOVEREIGNTY_HUB_GROUP_ID)
        .select_related("eve_group")
        .order_by("name")
    )
