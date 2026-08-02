"""
Discord ↔ auth.Group sync signals.

Contract: Discord roles MUST be accurate. Django group membership only
changes when the corresponding Discord role mutate succeeds (fail-closed).
See docs/auth/discord-groups.md.
"""

import logging

from django.contrib.auth.models import Group, User
from django.db import IntegrityError
from django.db.models import signals
from django.dispatch import receiver

from discord.client import DiscordClient
from discord.exceptions import DiscordRoleAssignmentError
from discord.helpers import (
    handle_discord_guild_member_error,
    is_discord_unknown_guild_member_error,
    remove_all_roles_from_guild_member,
)
from discord.sync_context import is_discord_group_sync_disabled

from .models import DiscordRole, DiscordUser

logger = logging.getLogger(__name__)
discord = DiscordClient()


@receiver(
    signals.pre_save,
    sender=DiscordRole,
    dispatch_uid="resolve_existing_discord_role_from_server",
)
def resolve_existing_discord_role_from_server(
    sender, instance, *args, **kwargs
):
    if instance.role_id:
        # Already linked to a Discord role (create or later updates).
        return

    roles = discord.get_roles()
    for role in roles:
        if role["name"] == instance.name:
            logger.info("Found existing role with name %s", instance.name)
            instance.role_id = role["id"]
            return

    logger.info(
        "No role_id, creating role based on group name %s",
        instance.group.name,
    )
    role = discord.create_role(instance.group.name)
    logger.info("External role created: %s", role.json())
    instance.role_id = role.json()["id"]


def _discord_role_id_for_name(name: str):
    """Return Discord role id for a role name if it already exists on the server."""
    for role in discord.get_roles():
        if role["name"] == name:
            return role["id"]
    return None


def _ensure_discord_role_for_group(group: Group) -> DiscordRole:
    """
    Ensure a DiscordRole row exists for this auth group.

    If Discord already has a role with this name and a DiscordRole row owns that
    role_id (e.g. leftover from a deleted/recreated group), re-point it instead
    of inserting a duplicate unique role_id.
    """
    existing = DiscordRole.objects.filter(group=group).first()
    if existing is not None:
        return existing

    role_id = _discord_role_id_for_name(group.name)
    if role_id is not None:
        claimed = DiscordRole.objects.filter(role_id=role_id).first()
        if claimed is not None:
            logger.info(
                "Re-linking DiscordRole role_id=%s from group %s to %s",
                role_id,
                claimed.group_id,
                group.id,
            )
            claimed.group = group
            claimed.name = group.name
            claimed.save(update_fields=["group", "name", "updated_at"])
            return claimed

    try:
        return DiscordRole.objects.create(name=group.name, group=group)
    except IntegrityError:
        # Concurrent create or race with role_id uniqueness — recover by role_id.
        role_id = role_id or _discord_role_id_for_name(group.name)
        if role_id is None:
            raise
        claimed = DiscordRole.objects.filter(role_id=role_id).first()
        if claimed is None:
            raise
        claimed.group = group
        claimed.name = group.name
        claimed.save(update_fields=["group", "name", "updated_at"])
        return claimed


@receiver(signals.post_save, sender=Group, dispatch_uid="group_post_save")
def group_post_save(
    sender, instance, created, **kwargs
):  # pylint: disable=unused-argument
    logger.info("Group saved, creating / updating role")
    _ensure_discord_role_for_group(instance)


def _discord_role_call(
    user, discord_user, role, *, add: bool, context: str
) -> bool:
    """
    Apply or remove a Discord role.

    Returns True on success.
    Returns False only when Discord reports unknown member (10007) — there is
    no Discord access left to leave behind.
    Raises DiscordRoleAssignmentError (or re-raises) for unreachable / 403 /
    other failures so Django M2M does not commit.
    """
    call = discord.add_user_role if add else discord.remove_user_role
    try:
        call(discord_user.id, role.role_id)
    except Exception as exc:
        if is_discord_unknown_guild_member_error(exc):
            handle_discord_guild_member_error(user, exc, context)
            return False
        # 403 and other handled errors must still abort membership changes.
        handle_discord_guild_member_error(
            user, exc, context, offboard_if_missing=False
        )
        raise DiscordRoleAssignmentError(
            f"Discord role {'add' if add else 'remove'} failed for "
            f"user={getattr(user, 'id', None)} role={role.name}: {exc}"
        ) from exc
    return True


def _discord_user_for(user):
    return getattr(user, "discord_user", None)


def _add_user_to_group_discord_role(user, group):
    """Fail-closed: raise unless Discord role is assigned (or already held)."""
    logger.info("User added to group, adding to discord role")
    discord_user = _discord_user_for(user)
    if discord_user is None:
        raise DiscordRoleAssignmentError(
            f"Cannot add user {user.id} to group {group.name}: no DiscordUser"
        )

    try:
        role = _ensure_discord_role_for_group(group)
    except Exception as exc:
        raise DiscordRoleAssignmentError(
            f"Cannot ensure DiscordRole for group {group.name}: {exc}"
        ) from exc

    if discord_user in role.members.all():
        logger.debug("User already in role, skipping")
        return

    logger.info(
        "Adding user %s to external discord role %s",
        discord_user,
        role,
    )
    if not _discord_role_call(
        user, discord_user, role, add=True, context="add_user_role"
    ):
        # Unknown member — offboard may have deleted the user; abort M2M.
        raise DiscordRoleAssignmentError(
            f"Cannot add user {user.id} to Discord role {role.name}: "
            "member not on Discord server"
        )
    role.members.add(discord_user)


def _remove_user_from_group_discord_role(user, group):
    """
    Fail-closed on Discord unreachable/403 so Django cannot drop tracking
    while Discord still has the role. Allows remove when there is nothing
    left on Discord (no DiscordUser, no DiscordRole, or 10007).
    """
    logger.info("User removed from group, removing from discord role")
    discord_user = _discord_user_for(user)
    if discord_user is None:
        logger.info("Group change without discord user")
        return

    role = DiscordRole.objects.filter(group=group).first()
    if role is None:
        logger.warning("No discord role for group %s", group.name)
        return

    if not _discord_role_call(
        user, discord_user, role, add=False, context="remove_user_role"
    ):
        # 10007 — no Discord access left; allow Django remove.
        role.members.remove(discord_user)
        return
    role.members.remove(discord_user)


def _user_group_pre_add(user, model, pk_set):
    for group_id in pk_set:
        group = model.objects.get(pk=group_id)
        _add_user_to_group_discord_role(user, group)


def _user_group_pre_remove(user, model, pk_set):
    for group_id in pk_set:
        group = model.objects.get(pk=group_id)
        _remove_user_from_group_discord_role(user, group)


def _user_group_pre_clear(user):
    logger.info("User removed from all groups, removing from discord roles")
    discord_user = _discord_user_for(user)
    if discord_user is None:
        logger.info("Group change without discord user")
        return
    # Snapshot roles before mutating membership tracking.
    roles = list(discord_user.groups.all())
    for role in roles:
        if not _discord_role_call(
            user,
            discord_user,
            role,
            add=False,
            context="clear_user_roles",
        ):
            role.members.remove(discord_user)
            continue
        role.members.remove(discord_user)


@receiver(
    signals.m2m_changed,
    sender=User.groups.through,
    dispatch_uid="user_group_changed",
)
def user_group_changed(
    sender, instance, action, reverse, model, pk_set, **kwargs
):  # pylint: disable=unused-argument
    """
    Mirror auth.Group membership to Discord roles (fail-closed).

    See docs/auth/discord-groups.md. Raises DiscordRoleAssignmentError from
    pre_add/pre_remove/pre_clear when Discord cannot be updated, which aborts
    the M2M change.
    """
    if is_discord_group_sync_disabled():
        return

    if action == "pre_add":
        if reverse:
            group = instance
            for user_id in pk_set:
                user = model.objects.get(pk=user_id)
                _add_user_to_group_discord_role(user, group)
        else:
            user = instance
            _user_group_pre_add(user, model, pk_set)
    elif action == "pre_remove":
        if reverse:
            group = instance
            for user_id in pk_set:
                user = model.objects.get(pk=user_id)
                _remove_user_from_group_discord_role(user, group)
        else:
            user = instance
            _user_group_pre_remove(user, model, pk_set)
    elif action == "pre_clear":
        if reverse:
            group = instance
            for user in group.user_set.all():
                _remove_user_from_group_discord_role(user, group)
        else:
            user = instance
            _user_group_pre_clear(user)


@receiver(
    signals.pre_delete,
    sender=DiscordUser,
    dispatch_uid="discord_user_deleting",
)
def discord_user_deleting(
    sender, instance, **kwargs
):  # pylint: disable=unused-argument
    logger.info("Discord user deleting, removing roles")
    remove_all_roles_from_guild_member(instance.id)
