"""Permission-check helpers for the tribes app."""

from groups.helpers.feature_access import can_use_feature
from tribes.models import TribeGroup, TribeGroupMembership

# Same feature the site's roster gate checks.
ROSTER_VIEW_FEATURE = "tribes.roster.view"


def user_can_view_alliance_rosters(user) -> bool:
    """Return True if the user may see alliance-visible rosters.

    This checks the tribes.roster.view feature, not alliance affiliation.
    """
    if not getattr(user, "is_authenticated", False) or not user.pk:
        return False
    return can_use_feature(user, ROSTER_VIEW_FEATURE)


# Old name; it never checked alliance membership. Prefer the name above.
user_is_alliance_member = user_can_view_alliance_rosters


def user_is_tribe_chief(user, tribe) -> bool:
    """Return True if user is the tribe chief or has superuser/perm override."""
    if user.is_superuser:
        return True
    if tribe.chief_id and tribe.chief_id == user.pk:
        return True
    return can_use_feature(user, "tribes.manage_memberships", tribe=tribe)


def user_can_manage_group(user, tribe_group: TribeGroup) -> bool:
    """
    Return True if the user can approve/deny memberships for a TribeGroup.
    Covers: tribe chief, group chief, superuser, or explicit perm.
    """
    if user.is_superuser:
        return True
    if can_use_feature(
        user, "tribes.manage_memberships", tribe_group=tribe_group
    ):
        return True
    tribe = tribe_group.tribe
    if tribe.chief_id and tribe.chief_id == user.pk:
        return True
    if tribe_group.chief_id and tribe_group.chief_id == user.pk:
        return True
    return False


def user_can_view_group_roster(user, tribe_group: TribeGroup) -> bool:
    """
    Return True if the user may see roster names and portraits.

    A hidden roster is limited to active members of that group and people
    who can manage it. Otherwise the roster stays alliance-visible.
    """
    if not getattr(user, "is_authenticated", False) or not user.pk:
        return False
    if tribe_group.roster_hidden:
        if user_can_manage_group(user, tribe_group):
            return True
        return user_in_tribe_group(user, tribe_group)
    return user_can_view_alliance_rosters(user)


def user_in_tribe_group(user, tribe_group: TribeGroup) -> bool:
    """Return True if the user has an active TribeGroupMembership in tribe_group."""
    return TribeGroupMembership.objects.filter(
        user=user,
        tribe_group=tribe_group,
        status=TribeGroupMembership.STATUS_ACTIVE,
    ).exists()


def user_is_active_tribe_member(user, tribe_id: int) -> bool:
    """Return True if the user has an active membership in any group of the tribe."""
    if not getattr(user, "is_authenticated", False) or not user.pk:
        return False
    return TribeGroupMembership.objects.filter(
        tribe_group__tribe_id=tribe_id,
        user_id=user.pk,
        status=TribeGroupMembership.STATUS_ACTIVE,
    ).exists()
