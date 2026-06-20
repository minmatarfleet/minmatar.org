import logging

from django.contrib.auth.models import Group, User
from django.db.models import signals
from django.dispatch import receiver

from discord.helpers import (
    handle_discord_guild_member_error,
    remove_all_roles_from_guild_member,
)
from discord.client import DiscordClient

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
    existing_role = False
    if not instance.role_id:  # skip when importing a role
        roles = discord.get_roles()
        for role in roles:
            if role["name"] == instance.name:
                logger.info("Found existing role with name %s", instance.name)
                instance.role_id = role["id"]
                existing_role = True
                break

    if not existing_role:
        logger.info(
            "No role_id, creating role based on group name %s",
            instance.group.name,
        )
        role = discord.create_role(instance.group.name)
        logger.info("External role created: %s", role.json())
        instance.role_id = role.json()["id"]


@receiver(signals.post_save, sender=Group, dispatch_uid="group_post_save")
def group_post_save(
    sender, instance, created, **kwargs
):  # pylint: disable=unused-argument
    logger.info("Group saved, creating / updating role")
    if not DiscordRole.objects.filter(group=instance).exists():
        DiscordRole.objects.create(
            name=instance.name,
            group=instance,
        )


def _discord_role_call(
    user, discord_user, role, *, add: bool, context: str
) -> bool:
    """Apply or remove a Discord role. Returns False if member missing on Discord."""
    call = discord.add_user_role if add else discord.remove_user_role
    try:
        call(discord_user.id, role.role_id)
    except Exception as exc:
        if handle_discord_guild_member_error(
            user, exc, context, offboard_if_missing=False
        ):
            return False
        raise
    return True


def _discord_user_for(user):
    return getattr(user, "discord_user", None)


def _add_user_to_group_discord_role(user, group):
    logger.info("User added to group, adding to discord role")
    discord_user = _discord_user_for(user)
    if discord_user is None:
        logger.error("Group change without discord user")
        return
    logger.debug("Checking group %s", group.name)
    if not DiscordRole.objects.filter(group=group).exists():
        logger.warning("No discord role for group %s", group.name)
        return
    if discord_user in group.discord_group.members.all():
        logger.debug("User already in role, skipping")
        return
    role = DiscordRole.objects.get(group=group)
    logger.info(
        "Adding user %s to external discord role %s",
        discord_user,
        role,
    )
    if not _discord_role_call(
        user, discord_user, role, add=True, context="add_user_role"
    ):
        return
    role.members.add(discord_user)


def _remove_user_from_group_discord_role(user, group):
    logger.info("User removed from group, removing from discord role")
    discord_user = _discord_user_for(user)
    if discord_user is None:
        logger.error("Group change without discord user")
        return
    if not DiscordRole.objects.filter(group=group).exists():
        logger.warning("No discord role for group %s", group.name)
        return
    role = DiscordRole.objects.get(group=group)
    if not _discord_role_call(
        user, discord_user, role, add=False, context="remove_user_role"
    ):
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
        logger.error("Group change without discord user")
        return
    for role in discord_user.groups.all():
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
    """Adds user to discord role when added to group"""
    if action == "pre_add":
        if reverse:
            group = instance
            for user_id in pk_set:
                user = model.objects.get(pk=user_id)
                _add_user_to_group_discord_role(user, group)
        else:
            user = instance
            if _discord_user_for(user) is None:
                logger.error("Group change without discord user")
                return
            _user_group_pre_add(user, model, pk_set)
    elif action == "pre_remove":
        if reverse:
            group = instance
            for user_id in pk_set:
                user = model.objects.get(pk=user_id)
                _remove_user_from_group_discord_role(user, group)
        else:
            user = instance
            if _discord_user_for(user) is None:
                logger.error("Group change without discord user")
                return
            _user_group_pre_remove(user, model, pk_set)
    elif action == "pre_clear":
        if reverse:
            group = instance
            for user in group.user_set.all():
                _remove_user_from_group_discord_role(user, group)
        else:
            user = instance
            if _discord_user_for(user) is None:
                logger.error("Group change without discord user")
                return
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
