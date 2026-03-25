import csv
import io
import logging

from django.contrib.auth.models import User

from app.celery import app
from discord.client import DiscordClient
from eveonline.helpers.characters import (
    user_primary_character,
)
from eveonline.models import EvePlayer

from .helpers import (
    process_bulk_community_status_row,
    sync_tribe_chief_group_membership,
)
from .models import (
    AffiliationType,
    EveCorporationGroup,
    UserAffiliation,
)

discord = DiscordClient()
logger = logging.getLogger(__name__)


@app.task
def bulk_update_community_status(
    csv_content: str, default_reason: str, changed_by_user_id: int
):
    """
    Process a bulk community status CSV in the background (updates status + Discord roles).
    csv_content: UTF-8 CSV with username, community_status, optional reason.
    default_reason: applied when row has no reason.
    changed_by_user_id: User pk for history.changed_by.
    """
    reader = csv.DictReader(io.StringIO(csv_content))
    if (
        not reader.fieldnames
        or "username" not in reader.fieldnames
        or "community_status" not in reader.fieldnames
    ):
        logger.warning("bulk_update_community_status: invalid CSV columns")
        return
    applied = 0
    not_found = []
    errors = []
    for i, row in enumerate(reader, start=2):
        did_apply, not_found_name, error_msg = (
            process_bulk_community_status_row(
                row, i, default_reason, changed_by_user_id
            )
        )
        if did_apply:
            applied += 1
        elif not_found_name:
            not_found.append(not_found_name)
        elif error_msg:
            errors.append(error_msg)
    logger.info(
        "bulk_update_community_status: applied=%s not_found=%s errors=%s",
        applied,
        len(not_found),
        len(errors),
    )
    if not_found:
        logger.info(
            "bulk_update_community_status not_found: %s", not_found[:20]
        )
    if errors:
        logger.warning("bulk_update_community_status errors: %s", errors[:10])


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
    logger.info("Checking affiliations for user %s", user)

    primary_character = user_primary_character(user)
    if not primary_character:
        logger.info("No primary character found for user %s", user)
        UserAffiliation.objects.filter(user=user).delete()
        return

    # loop through affiliations in priority to find highest qualifying
    for affiliation in AffiliationType.objects.order_by("-priority"):
        logger.info("Checking if qualified for affiliation %s", affiliation)
        is_qualifying = False
        if affiliation.default:
            is_qualifying = True
        if (
            primary_character.corporation_id
            and affiliation.corporations.filter(
                corporation_id=primary_character.corporation_id
            ).exists()
        ):
            logger.info(
                "User %s is in corporation %s",
                user,
                primary_character.corporation_id,
            )
            is_qualifying = True

        if (
            primary_character.alliance_id
            and affiliation.alliances.filter(
                alliance_id=primary_character.alliance_id
            ).exists()
        ):
            logger.info(
                "User %s is in alliance %s",
                user,
                primary_character.alliance_id,
            )
            is_qualifying = True

        if (
            primary_character.faction_id
            and affiliation.factions.filter(
                id=primary_character.faction_id
            ).exists()
        ):
            logger.info(
                "User %s is in faction %s",
                user,
                primary_character.faction_id,
            )
            is_qualifying = True

        if is_qualifying:
            logger.info(
                "User %s qualifies for affiliation %s",
                user,
                affiliation,
            )
            if UserAffiliation.objects.filter(
                user=user, affiliation=affiliation
            ).exists():
                logger.info(
                    "User %s already has affiliation %s",
                    user,
                    affiliation,
                )
                return

            if UserAffiliation.objects.filter(user=user).exists():
                logger.info(
                    "User %s already has an affiliation, removing",
                    user,
                )
                UserAffiliation.objects.filter(user=user).delete()

            logger.info(
                "Creating affiliation for user %s with %s",
                user,
                affiliation,
            )
            UserAffiliation.objects.create(user=user, affiliation=affiliation)
            return
        else:
            logger.info(
                "User %s does not qualify for affiliation %s",
                user,
                affiliation,
            )
            if UserAffiliation.objects.filter(
                user=user, affiliation=affiliation
            ).exists():
                logger.info(
                    "User %s has affiliation %s, removing",
                    user,
                    affiliation,
                )
                UserAffiliation.objects.filter(
                    user=user, affiliation=affiliation
                ).delete()
            else:
                logger.info(
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
        logger.info("Couldn't update affiliations for unlinked user %s", user)


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
        if not primary or primary.corporation_id is None:
            return False
        return primary.corporation_id == corp.corporation_id

    if group_type == EveCorporationGroup.GROUP_TYPE_RECRUITER:
        return corp.recruiters.filter(user=user).exists()
    if group_type == EveCorporationGroup.GROUP_TYPE_DIRECTOR:
        return corp.directors.filter(user=user).exists()
    # Gunner group = stewards / station managers
    if group_type == EveCorporationGroup.GROUP_TYPE_GUNNER:
        return corp.stewards.filter(user=user).exists()

    return False


def _user_qualifies_cached(
    user_id,
    corporation_group,
    user_primary_corp,
    recruiter_user_ids,
    director_user_ids,
    steward_user_ids,
):
    """
    Same logic as _user_qualifies_for_corporation_group but using
    pre-fetched data (no DB queries).
    """
    corp = corporation_group.corporation
    group_type = (
        corporation_group.group_type or EveCorporationGroup.GROUP_TYPE_MEMBER
    )

    if group_type == EveCorporationGroup.GROUP_TYPE_MEMBER:
        primary_corp_id = user_primary_corp.get(user_id)
        if primary_corp_id is None:
            return False
        return primary_corp_id == corp.corporation_id

    if group_type == EveCorporationGroup.GROUP_TYPE_RECRUITER:
        return user_id in recruiter_user_ids
    if group_type == EveCorporationGroup.GROUP_TYPE_DIRECTOR:
        return user_id in director_user_ids
    if group_type == EveCorporationGroup.GROUP_TYPE_GUNNER:
        return user_id in steward_user_ids

    return False


@app.task
def sync_eve_corporation_groups():
    """
    Sync Django auth group membership for corporation groups based on
    character ownership: member = primary in corp, recruiter/director/gunner
    = character in corp's role set.
    Uses bulk lookups to avoid N+1 queries.
    """
    user_primary_corp = dict(
        EvePlayer.objects.filter(primary_character__isnull=False).values_list(
            "user_id", "primary_character__corporation_id"
        )
    )

    for corporation_group in EveCorporationGroup.objects.select_related(
        "corporation", "group"
    ):
        if not corporation_group.corporation:
            logger.error(
                "Corporation group found with no corporation",
            )
            continue

        corp = corporation_group.corporation
        group = corporation_group.group

        in_group_user_ids = set(group.user_set.values_list("id", flat=True))
        recruiter_user_ids = set(
            corp.recruiters.values_list("user_id", flat=True)
        )
        director_user_ids = set(
            corp.directors.values_list("user_id", flat=True)
        )
        steward_user_ids = set(corp.stewards.values_list("user_id", flat=True))

        for user in User.objects.all():
            try:
                in_group = user.id in in_group_user_ids
                qualifies = _user_qualifies_cached(
                    user.id,
                    corporation_group,
                    user_primary_corp,
                    recruiter_user_ids,
                    director_user_ids,
                    steward_user_ids,
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


@app.task
def sync_tribe_chief_group():
    """Ensure Tribe - Chief auth group exists and matches active tribe chiefs."""
    sync_tribe_chief_group_membership()
