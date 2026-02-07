import logging

from django.contrib.auth.models import User

from app.celery import app
from discord.client import DiscordClient
from eveonline.helpers.characters import (
    user_primary_character,
)

from .models import (
    AffiliationType,
    EveCorporationGroup,
    Sig,
    SigRequest,
    Team,
    TeamRequest,
    UserAffiliation,
)

discord = DiscordClient()
logger = logging.getLogger(__name__)


@app.task
def update_affiliations():
    for user in User.objects.all():
        try:
            update_affiliation(user.id)
        except Exception as e:
            log_affiliation_update_error(user, e)


@app.task
def update_affiliation(user_id: int):
    user = User.objects.get(id=user_id)
    logger.debug("Checking affiliations for user %s", user)

    primary_character = user_primary_character(user)
    if not primary_character:
        logger.warning("No primary character found for user %s", user)
        UserAffiliation.objects.filter(user=user).delete()
        return

    # loop through affiliations in priority to find highest qualifying
    for affiliation in AffiliationType.objects.order_by("-priority"):
        logger.debug("Checking if qualified for affiliation %s", affiliation)
        is_qualifying = False
        if affiliation.default:
            is_qualifying = True
        if primary_character.corporation in affiliation.corporations.all():
            logger.debug(
                "User %s is in corporation %s",
                user,
                primary_character.corporation,
            )

            is_qualifying = True

        if primary_character.alliance in affiliation.alliances.all():
            logger.debug(
                "User %s is in alliance %s",
                user,
                primary_character.alliance,
            )
            is_qualifying = True

        if primary_character.faction in affiliation.factions.all():
            logger.debug(
                "User %s is in faction %s",
                user,
                primary_character.faction,
            )
            is_qualifying = True

        if is_qualifying:
            logger.debug(
                "User %s qualifies for affiliation %s",
                user,
                affiliation,
            )
            if UserAffiliation.objects.filter(
                user=user, affiliation=affiliation
            ).exists():
                logger.debug(
                    "User %s already has affiliation %s",
                    user,
                    affiliation,
                )
                return

            if UserAffiliation.objects.filter(user=user).exists():
                logger.debug(
                    "User %s already has an affiliation, removing",
                    user,
                )
                UserAffiliation.objects.filter(user=user).delete()

            logger.debug(
                "Creating affiliation for user %s with %s",
                user,
                affiliation,
            )
            UserAffiliation.objects.create(user=user, affiliation=affiliation)
            return
        else:
            logger.debug(
                "User %s does not qualify for affiliation %s",
                user,
                affiliation,
            )
            if UserAffiliation.objects.filter(
                user=user, affiliation=affiliation
            ).exists():
                logger.debug(
                    "User %s has affiliation %s, removing",
                    user,
                    affiliation,
                )
                UserAffiliation.objects.filter(
                    user=user, affiliation=affiliation
                ).delete()
            else:
                logger.debug(
                    "User %s does not have affiliation %s",
                    user,
                    affiliation,
                )
                continue


def log_affiliation_update_error(user: User, e):
    if user_primary_character(user):
        logger.error("Error updating affiliations for user %s: %s", user, e)
    else:
        # If user has no primary character then assume it isn't important.
        # We were ignoring these anyway, so no point logging them as errors.
        logger.debug("Couldn't update affiliations for unlinked user %s", user)


def _user_qualifies_for_corporation_group(user, corporation_group):
    """
    Return True if this user should be in the given corporation group
    based on group_type and character ownership.
    """
    corp = corporation_group.corporation
    group_type = (
        corporation_group.group_type or EveCorporationGroup.GROUP_TYPE_MEMBER
    )

    if group_type == EveCorporationGroup.GROUP_TYPE_MEMBER:
        primary = user_primary_character(user)
        if not primary or not primary.corporation:
            return False
        return primary.corporation.id == corp.id

    if group_type == EveCorporationGroup.GROUP_TYPE_RECRUITER:
        return corp.recruiters.filter(user=user).exists()
    if group_type == EveCorporationGroup.GROUP_TYPE_DIRECTOR:
        return corp.directors.filter(user=user).exists()
    # Gunner group = stewards / station managers
    if group_type == EveCorporationGroup.GROUP_TYPE_GUNNER:
        return corp.stewards.filter(user=user).exists()

    return False


@app.task
def sync_eve_corporation_groups():
    """
    Sync Django auth group membership for corporation groups based on
    character ownership: member = primary in corp, recruiter/director/gunner
    = character in corp's role set.
    """
    for corporation_group in EveCorporationGroup.objects.select_related(
        "corporation", "group"
    ):
        if not corporation_group.corporation:
            logger.error(
                "Corporation group found with no corporation",
            )
            continue

        group = corporation_group.group
        for user in User.objects.all():
            try:
                in_group = group in user.groups.all()
                qualifies = _user_qualifies_for_corporation_group(
                    user, corporation_group
                )

                if qualifies and not in_group:
                    logger.info(
                        "User %s qualifies for corporation group %s, adding",
                        user,
                        group.name,
                    )
                    user.groups.add(group)
                elif not qualifies and in_group:
                    logger.info(
                        "User %s no longer qualifies for corporation group %s, removing",
                        user,
                        group.name,
                    )
                    user.groups.remove(group)
            except Exception as e:
                logger.error(
                    "Error syncing corporation group %s for user %s: %s",
                    corporation_group,
                    user,
                    e,
                )
                continue


@app.task()
def create_team_request_reminders():
    for team in Team.objects.all():
        if not team.discord_channel_id:
            logger.info("Team %s has no discord channel", team)
            continue

        if not TeamRequest.objects.filter(approved=None, team=team).exists():
            logger.info("Team %s has no pending requests", team)
            continue

        message = "**Pending Request Notifications**\n"
        for team_request in TeamRequest.objects.filter(
            approved=None, team=team
        ):
            message += f"- <@{team_request.user.discord_user.id}>\n"

        message += "Please review and approve or deny these requests [here](https://my.minmatar.org/alliance/teams/requests/).\n"

        director_mentions = ""
        for user in team.directors.all():
            director_mentions += f"<@{user.discord_user.id}> "
        if director_mentions:
            message += f"{director_mentions}\n"

        discord.create_message(team.discord_channel_id, message)


@app.task()
def create_sig_request_reminders():
    for sig in Sig.objects.all():
        if not sig.discord_channel_id:
            logger.info("Sig %s has no discord channel", sig)
            continue

        if not SigRequest.objects.filter(approved=None, sig=sig).exists():
            logger.info("Sig %s has no pending requests", sig)
            continue

        message = "**Pending Request Notifications**\n"
        for sig_request in SigRequest.objects.filter(approved=None, sig=sig):
            message += f"- <@{sig_request.user.discord_user.id}>\n"

        message += "Please review and approve or deny these requests [here](https://my.minmatar.org/alliance/sigs/requests/).\n"

        officer_mentions = ""
        for user in sig.officers.all():
            officer_mentions += f"<@{user.discord_user.id}> "
        if officer_mentions:
            message += f"{officer_mentions}\n"

        discord.create_message(sig.discord_channel_id, message)


@app.task()
def remove_sigs():
    """
    Remove all sigs for users that don't have the required permissions to request sigs
    """
    for sig in Sig.objects.all():
        for user in sig.members.all():
            try:
                if not user.has_perm("groups.add_sigrequest"):
                    sig.members.remove(user)
                    logger.info("Removing user %s from sig %s", user, sig)
            except Exception as e:
                logger.error(
                    "Error removing user %s from sig %s: %s", user, sig, e
                )
                continue


@app.task()
def remove_teams():
    """
    Remove all teams for users that don't have the required permissions to request teams
    """
    for team in Team.objects.all():
        for user in team.members.all():
            try:
                if not user.has_perm("groups.add_teamrequest"):
                    team.members.remove(user)
                    logger.info("Removing user %s from team %s", user, team)
            except Exception as e:
                logger.error(
                    "Error removing user %s from team %s: %s", user, team, e
                )
                continue
