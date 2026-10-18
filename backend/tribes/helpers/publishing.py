"""Who may publish as a tribe group, and who sees what it publishes.

The contract is docs/tribes/tribe-publishing.md ("Permissions").
"""

from __future__ import annotations

from groups.helpers.feature_access import feature_batch
from tribes.helpers.permissions import user_can_manage_group
from tribes.models import TribeGroup, TribeGroupMembership

KIND_POST = "post"
KIND_FLEET = "fleet"
KIND_EVENT = "event"
KINDS = (KIND_POST, KIND_FLEET, KIND_EVENT)

_POLICY_FIELD = {
    KIND_POST: "post_policy",
    KIND_FLEET: "fleet_policy",
    KIND_EVENT: "event_policy",
}
_PUBLISHERS_FIELD = {
    KIND_POST: "post_publishers",
    KIND_FLEET: "fleet_publishers",
    KIND_EVENT: "event_publishers",
}


def _authenticated(user) -> bool:
    return bool(getattr(user, "is_authenticated", False) and user.pk)


def is_active_member(user, group: TribeGroup) -> bool:
    """True when the user has an active membership in the group."""
    if not _authenticated(user):
        return False
    return TribeGroupMembership.objects.filter(
        user_id=user.pk,
        tribe_group_id=group.pk,
        status=TribeGroupMembership.STATUS_ACTIVE,
    ).exists()


def active_member_group_ids(user) -> frozenset[int]:
    """Ids of the groups the user is an active member of."""
    if not _authenticated(user):
        return frozenset()
    return frozenset(
        TribeGroupMembership.objects.filter(
            user_id=user.pk, status=TribeGroupMembership.STATUS_ACTIVE
        ).values_list("tribe_group_id", flat=True)
    )


def can_manage(user, group: TribeGroup) -> bool:
    if not _authenticated(user):
        return False
    return user_can_manage_group(user, group)


def can_publish(
    user,
    group: TribeGroup,
    kind: str,
    *,
    is_member: bool | None = None,
    manages: bool | None = None,
) -> bool:
    """May the user publish a post, fleet or event as this group?

    Managers always can. Otherwise the kind's policy decides: ``members``
    lets every active member publish, ``chosen`` only the active members
    picked in that kind's publisher list, ``chiefs`` nobody else.
    ``is_member`` and ``manages`` let callers that already know skip the
    lookups.
    """
    if kind not in KINDS:
        raise ValueError(f"Unknown publishing kind {kind!r}")
    if not _authenticated(user) or not group.is_active:
        return False
    if manages is None:
        manages = can_manage(user, group)
    if manages:
        return True
    policy = getattr(group, _POLICY_FIELD[kind])
    if policy == TribeGroup.POLICY_CHIEFS:
        return False
    if is_member is None:
        is_member = is_active_member(user, group)
    if not is_member:
        return False
    if policy == TribeGroup.POLICY_MEMBERS:
        return True
    if policy == TribeGroup.POLICY_CHOSEN:
        return (
            getattr(group, _PUBLISHERS_FIELD[kind]).filter(pk=user.pk).exists()
        )
    return False


def publishable_groups(user, kind: str) -> list[TribeGroup]:
    """Active groups the user may publish this kind of item as."""
    if not _authenticated(user):
        return []
    member_ids = active_member_group_ids(user)
    groups = TribeGroup.objects.filter(is_active=True).select_related("tribe")
    with feature_batch(user):
        return [
            group
            for group in groups
            if can_publish(user, group, kind, is_member=group.pk in member_ids)
        ]


def visible_group_ids(user) -> frozenset[int]:
    """Groups whose members-only items the user may see.

    Active member of, or can manage; every group for a superuser.
    """
    if not _authenticated(user):
        return frozenset()
    if user.is_superuser:
        return frozenset(TribeGroup.objects.values_list("pk", flat=True))
    ids = set(active_member_group_ids(user))
    with feature_batch(user):
        for group in TribeGroup.objects.select_related("tribe"):
            if group.pk not in ids and user_can_manage_group(user, group):
                ids.add(group.pk)
    return frozenset(ids)


def can_view_group_items(user, group: TribeGroup) -> bool:
    """May the user see the group's members-only items?"""
    if not _authenticated(user):
        return False
    if user.is_superuser:
        return True
    return is_active_member(user, group) or user_can_manage_group(user, group)


def fleet_visible_to(user, fleet) -> bool:
    """Group fleet visibility for one fleet (see visible_fleets_q)."""
    if not fleet.host_group_id or fleet.open_to_alliance:
        return True
    if not _authenticated(user):
        return False
    if fleet.created_by_id and fleet.created_by_id == user.pk:
        return True
    return can_view_group_items(user, fleet.host_group)


def post_visible_to(user, post) -> bool:
    """Members-only posts are for the host group, its managers and the
    author."""
    if not post.members_only:
        return True
    if not _authenticated(user):
        return False
    if post.user_id == user.pk:
        return True
    if not post.host_group_id:
        return False
    return can_view_group_items(user, post.host_group)


def host_group_ref(group: TribeGroup | None) -> dict | None:
    """The HostGroupRef shape: {id, code, name, tribe_id, tribe_name}."""
    if group is None:
        return None
    return {
        "id": group.pk,
        "code": group.code or "",
        "name": group.name,
        "tribe_id": group.tribe_id,
        "tribe_name": group.tribe.name,
    }


def _discord_role(group: TribeGroup):
    auth_group = group.group
    if auth_group is None:
        return None
    try:
        return auth_group.discord_group
    except auth_group.__class__.discord_group.RelatedObjectDoesNotExist:
        return None


def group_role_mention(group: TribeGroup) -> str:
    """``<@&role_id>`` for the group's Discord role, or "" without one."""
    role = _discord_role(group)
    if role is None or not role.role_id:
        return ""
    return f"<@&{role.role_id}>"


def group_role_name(group: TribeGroup) -> str | None:
    """The mentioned role's name (the auth group name), None without one."""
    role = _discord_role(group)
    if role is None:
        return None
    return group.group.name


def group_page_path(group: TribeGroup) -> str:
    return f"/alliance/tribes/{group.tribe_id}/{group.pk}/"
