import logging

from django.contrib.auth.models import Group, User
from django.db.models import signals
from django.dispatch import receiver

from discord.client import DiscordClient

from .models import DiscordRole

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
    if not instance.role_id:  # skip when importing a role
        roles = discord.get_roles()
        existing_role = False
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
    if DiscordRole.objects.filter(group=instance).exists():
        role = DiscordRole.objects.get(group=instance)
        role.name = instance.name
        role.save()
    else:
        DiscordRole.objects.create(
            name=instance.name,
            group=instance,
        )


@receiver(
    signals.m2m_changed,
    sender=User.groups.through,
    dispatch_uid="user_group_changed",
)
def user_group_changed(
    sender, instance, action, reverse, **kwargs
):  # pylint: disable=unused-argument
    """Adds user to discord role when added to group"""
    if action == "post_add":
        logger.info("User added to group, adding to discord role")
        for group in instance.groups.all():
            if DiscordRole.objects.filter(group=group).exists():
                discord_user = instance.discord_user
                # check if discord_user in role members
                if discord_user in group.discord_group.members.all():
                    logger.info("User already in role, skipping")
                    continue

                role = DiscordRole.objects.get(group=group)
                discord.add_user_role(discord_user.id, role.role_id)
            else:
                logger.info("No discord role for group %s", group.name)
    elif action == "pre_remove":
        logger.info("User removed from group, removing from discord role")
        for group in instance.groups.all():
            if DiscordRole.objects.filter(group=group).exists():
                discord_user = instance.discord_user
                role = DiscordRole.objects.get(group=group)
                discord.remove_user_role(discord_user.id, role.role_id)
            else:
                logger.info("No discord role for group %s", group.name)
    elif action == "pre_clear":
        logger.info(
            "User removed from all groups, removing from discord roles"
        )
        discord_user = instance.discord_user
        for role in discord_user.groups.all():
            discord.remove_user_role(discord_user.id, role.role_id)
