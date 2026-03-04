"""Permission-check helpers for the tribes app."""

from tribes.models import TribeGroup, TribeGroupMembership


def user_is_tribe_chief(user, tribe) -> bool:
    """Return True if user is the tribe chief or has superuser/perm override."""
    if user.is_superuser:
        return True
    if tribe.chief_id and tribe.chief_id == user.pk:
        return True
    return user.has_perm("tribes.change_tribegroupmembership")


def user_can_manage_group(user, tribe_group: TribeGroup) -> bool:
    """
    Return True if the user can approve/deny memberships for a TribeGroup.
    Covers: tribe chief, group chief, group elder, superuser, or explicit perm.
    """
    if user.is_superuser:
        return True
    if user.has_perm("tribes.change_tribegroupmembership"):
        return True
    tribe = tribe_group.tribe
    if tribe.chief_id and tribe.chief_id == user.pk:
        return True
    if tribe_group.chief_id and tribe_group.chief_id == user.pk:
        return True
    if tribe_group.elders.filter(pk=user.pk).exists():
        return True
    return False


def user_in_tribe_group(user, tribe_group: TribeGroup) -> bool:
    """Return True if the user has an active TribeGroupMembership in tribe_group."""
    return TribeGroupMembership.objects.filter(
        user=user,
        tribe_group=tribe_group,
        status=TribeGroupMembership.STATUS_ACTIVE,
    ).exists()
