from django.db.models import signals
from django.dispatch import receiver
from django.contrib.auth.models import Group, User
from .models import DiscordRole
from discord.client import DiscordClient
import logging

logger = logging.getLogger(__name__)
discord = DiscordClient()


@receiver(signals.post_save, sender=Group)
def group_post_save(sender, instance, created, **kwargs):
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


@receiver(signals.m2m_changed, sender=User.groups.through)
def user_group_changed(sender, instance, action, reverse, **kwargs):
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
