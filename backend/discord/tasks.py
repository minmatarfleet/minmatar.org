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
def sync_discord_user_roles(discord_user_id: int):
    discord_user = DiscordUser.objects.get(id=discord_user_id)
    user = discord_user.user
    expected_discord_roles = DiscordRole.objects.filter(
        group__in=user.groups.all()
    )

    for expected_discord_role in expected_discord_roles:
        logger.info(
            "Checking if user %s has external role %s",
            user.username,
            expected_discord_role.name,
        )
        if discord_user in expected_discord_role.members.all():
            continue
        discord.add_user_role(discord_user_id, expected_discord_role.role_id)
        discord_user.members.add(expected_discord_role)


@app.task()
def migrate_users():  # noqa
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
        try:
            discord_roles = discord.get_user(discord_user_id)["roles"]
        except Exception as e:
            logger.error(
                "Failed to get roles for user %s: %s", discord_user_id, e
            )
            continue

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
                team = Team.objects.get(group=group)
                if team.members.filter(username=user.username).exists():
                    logger.info(
                        "User %s already in team %s",
                        user.username,
                        group.name,
                    )
                    continue
                logger.info(
                    "Adding user %s to team %s", user.username, group.name
                )
                team = Team.objects.get(group=group)
                team.members.add(user)
                continue

            # check if sig
            if Sig.objects.filter(group=group).exists():
                sig = Sig.objects.get(group=group)
                if sig.members.filter(username=user.username).exists():
                    logger.info(
                        "User %s already in sig %s",
                        user.username,
                        group.name,
                    )
                    continue
                logger.info(
                    "Adding user %s to sig %s", user.username, group.name
                )
                sig = Sig.objects.get(group=group)
                sig.members.add(user)
                continue

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
                continue

            # add to group
            if Group.objects.filter(name=group.name).exists():
                if group.name == "Strategic FC" or group.name == "Skirmish FC":
                    fc_default_group = Group.objects.get(name="FC")
                    user.groups.add(fc_default_group)
                group = Group.objects.get(name=group.name)
                user.groups.add(group)
                logger.info(
                    "Adding user %s to group %s", user.username, group.name
                )

        # sync discord role members
        for discord_role_id in discord_roles:
            if not DiscordRole.objects.filter(
                role_id=discord_role_id
            ).exists():
                continue

            discord_role = DiscordRole.objects.get(role_id=discord_role_id)
            group = discord_role.group
            if group in user.groups.all():
                discord_user = DiscordUser.objects.get(user_id=user.id)
                if discord_user in discord_role.members.all():
                    logger.info("User already in role, skipping")
                    continue

                discord_role.members.add(discord_user)

    logger.info("Skipped users: %s", skipped_users)
    logger.info("Skipped roles: %s", skipped_roles)


@app.task()
def migrate_user(username: str):
    # users already have these groups
    signals.m2m_changed.disconnect(
        sender=User.groups.through,
        dispatch_uid="user_group_changed",
    )
    user = User.objects.get(username=username)
    time.sleep(1)
    if not DiscordUser.objects.filter(user_id=user.id).exists():
        logger.info(
            "Skipping migration of user %s, missing primary character",
            user.id,
        )
        return
    if not EvePrimaryCharacter.objects.filter(
        character__token__user__id=user.id
    ).exists():
        logger.info(
            "Skipping migration of user %s, missing primary character",
            user.id,
        )
        return

    discord_user = DiscordUser.objects.get(user_id=user.id)
    discord_user_id = discord_user.id
    discord_roles = discord.get_user(discord_user_id)["roles"]

    for discord_role_id in discord_roles:
        if not DiscordRole.objects.filter(role_id=discord_role_id).exists():
            logger.info("Skipping migration of role %s", discord_role_id)
            return

        discord_role = DiscordRole.objects.get(role_id=discord_role_id)
        group = discord_role.group

        # check if team
        if Team.objects.filter(group=group).exists():
            logger.info("Adding user %s to team %s", user.username, group.name)
            team = Team.objects.get(group=group)
            team.members.add(user)

        # check if sig
        if Sig.objects.filter(group=group).exists():
            logger.info("Adding user %s to sig %s", user.username, group.name)
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
