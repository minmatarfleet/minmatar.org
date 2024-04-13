import logging
import time

from django.contrib.auth.models import Group, User
from django.db.models import signals

from app.celery import app
from discord.client import DiscordClient
from eveonline.models import EvePrimaryCharacter
from groups.models import AffiliationType, Sig, Team, UserAffiliation

from .models import DiscordRole, DiscordUser

discord = DiscordClient()
logger = logging.getLogger(__name__)


@app.task()
def import_external_roles():
    roles = discord.get_roles()
    for role in roles:
        if role["managed"]:
            continue
        if role["name"] == "@everyone":
            continue
        if not Group.objects.filter(name=role["name"]).exists():
            Group.objects.create(name=role["name"])


@app.task()
def migrate_users():
    # users already have these groups
    signals.m2m_changed.disconnect(
        sender=User.groups.through,
        dispatch_uid="user_group_changed",
    )
    skipped_users = []
    skipped_roles = []
    for user in User.objects.all():
        time.sleep(1)
        if not DiscordUser.objects.filter(user_id=user.id).exists():
            logger.info(
                "Skipping migration of user %s, missing primary character",
                user.id,
            )
            skipped_users.append(user.username)
            continue

        if not EvePrimaryCharacter.objects.filter(
            character__token__user__id=user.id
        ).exists():
            logger.info(
                "Skipping migration of user %s, missing primary character",
                user.id,
            )
            skipped_users.append(user.username)
            continue

        discord_user = DiscordUser.objects.get(user_id=user.id)
        discord_user_id = discord_user.id
        discord_roles = discord.get_user(discord_user_id)["roles"]

        for discord_role_id in discord_roles:
            if not DiscordRole.objects.filter(
                role_id=discord_role_id
            ).exists():
                logger.info("Skipping migration of role %s", discord_role_id)
                skipped_roles.append(discord_role_id)
                continue

            discord_role = DiscordRole.objects.get(role_id=discord_role_id)
            group = discord_role.group

            # check if team
            if Team.objects.filter(group=group).exists():
                logger.info(
                    "Adding user %s to team %s", user.username, group.name
                )
                team = Team.objects.get(group=group)
                team.members.add(user)

            # check if sig
            if Sig.objects.filter(group=group).exists():
                logger.info(
                    "Adding user %s to sig %s", user.username, group.name
                )
                sig = Sig.objects.get(group=group)
                sig.members.add(user)

            # check if affiliation
            if AffiliationType.objects.filter(group=group).exists():
                logger.info(
                    "Adding user %s to affiliation %s",
                    user.username,
                    group.name,
                )
                affiliation_type = AffiliationType.objects.get(group=group)
                if UserAffiliation.objects.filter(
                    user=user, affiliation=affiliation_type
                ).exists():
                    logger.info(
                        "User %s already has affiliation %s",
                        user.username,
                        affiliation_type.name,
                    )
                    continue
                elif UserAffiliation.objects.filter(user=user).exists():
                    UserAffiliation.objects.filter(user=user).delete()
                UserAffiliation.objects.create(
                    user=user,
                    affiliation=affiliation_type,
                )

    logger.info("Skipped users: %s", skipped_users)
    logger.info("Skipped roles: %s", skipped_roles)
