"""
Celery tasks for the tribes app.

Tasks:
- sync_tribe_activities: ESI-sourced activity ingestion into TribeActivity.
- create_tribe_membership_reminders: Discord reminders for pending memberships.
- remove_tribe_members_without_permission: Removes members lacking base permission.
"""

import logging
from collections import defaultdict

from django.utils import timezone

from app.celery import app
from discord.client import DiscordClient
from eveonline.models.characters import (
    EveCharacterContract,
    EveCharacterIndustryJob,
    EveCharacterKillmail,
    EveCharacterKillmailAttacker,
    EveCharacterMiningEntry,
)
from fleets.models import EveFleetInstanceMember

from tribes.models import (
    TribeActivity,
    TribeGroup,
    TribeGroupMembership,
    TribeGroupMembershipCharacter,
)

discord = DiscordClient()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _already_ingested(reference_type: str, reference_id: str) -> bool:
    """Return True if a TribeActivity with this reference already exists."""
    return TribeActivity.objects.filter(
        reference_type=reference_type, reference_id=reference_id
    ).exists()


def _create_activity(
    tribe_group,
    user,
    character,
    activity_type: str,
    quantity: float,
    unit: str,
    description: str,
    reference_type: str,
    reference_id: str,
):
    if reference_id and _already_ingested(reference_type, reference_id):
        return
    TribeActivity.objects.create(
        tribe_group=tribe_group,
        user=user,
        character=character,
        activity_type=activity_type,
        quantity=quantity,
        unit=unit,
        description=description,
        reference_type=reference_type,
        reference_id=reference_id,
    )


def _committed_characters_for_group(tribe_group: TribeGroup):
    """
    Yield (character, user) pairs for all currently active committed characters
    in the given TribeGroup.
    """
    active_chars = TribeGroupMembershipCharacter.objects.filter(
        membership__tribe_group=tribe_group,
        membership__status=TribeGroupMembership.STATUS_APPROVED,
        left_at__isnull=True,
    ).select_related("character", "character__user", "membership__user")

    for tc in active_chars:
        yield tc.character, tc.membership.user


# ---------------------------------------------------------------------------
# Fleet participation
# ---------------------------------------------------------------------------


def _sync_fleet_participation(tribe_group: TribeGroup):
    ship_type_ids = set(tribe_group.ship_type_ids or [])
    if not ship_type_ids:
        return

    committed = {
        c.character_id: (c, u)
        for c, u in _committed_characters_for_group(tribe_group)
    }
    if not committed:
        return

    character_ids = set(committed.keys())
    fleet_members = EveFleetInstanceMember.objects.filter(
        character_id__in=character_ids,
        ship_type_id__in=ship_type_ids,
    ).select_related("eve_fleet_instance")

    for fm in fleet_members:
        character, user = committed[fm.character_id]
        ref_id = f"{fm.eve_fleet_instance_id}:{fm.character_id}"
        _create_activity(
            tribe_group=tribe_group,
            user=user,
            character=character,
            activity_type=TribeActivity.ACTIVITY_FLEET_PARTICIPATION,
            quantity=1,
            unit="fleets",
            description=f"Fleet participation in instance {fm.eve_fleet_instance_id}",
            reference_type="EveFleetInstanceMember",
            reference_id=ref_id,
        )


# ---------------------------------------------------------------------------
# Kills
# ---------------------------------------------------------------------------


def _sync_kills(tribe_group: TribeGroup):

    ship_type_ids = set(tribe_group.ship_type_ids or [])
    if not ship_type_ids:
        return

    committed = {
        c.character_id: (c, u)
        for c, u in _committed_characters_for_group(tribe_group)
    }
    if not committed:
        return

    character_ids = set(committed.keys())
    attackers = EveCharacterKillmailAttacker.objects.filter(
        character_id__in=character_ids,
        ship_type_id__in=ship_type_ids,
    ).select_related("killmail")

    for att in attackers:
        character, user = committed[att.character_id]
        ref_id = f"{att.killmail_id}:{att.character_id}"
        _create_activity(
            tribe_group=tribe_group,
            user=user,
            character=character,
            activity_type=TribeActivity.ACTIVITY_KILLS,
            quantity=1,
            unit="kills",
            description=f"Kill on killmail {att.killmail_id}",
            reference_type="EveCharacterKillmailAttacker",
            reference_id=ref_id,
        )


# ---------------------------------------------------------------------------
# Losses
# ---------------------------------------------------------------------------


def _sync_losses(tribe_group: TribeGroup):

    ship_type_ids = set(tribe_group.ship_type_ids or [])
    if not ship_type_ids:
        return

    committed = {
        c.character_id: (c, u)
        for c, u in _committed_characters_for_group(tribe_group)
    }
    if not committed:
        return

    character_ids = set(committed.keys())
    losses = EveCharacterKillmail.objects.filter(
        victim_character_id__in=character_ids,
        ship_type_id__in=ship_type_ids,
    )

    for loss in losses:
        character, user = committed[loss.victim_character_id]
        ref_id = str(loss.killmail_id)
        _create_activity(
            tribe_group=tribe_group,
            user=user,
            character=character,
            activity_type=TribeActivity.ACTIVITY_LOSSES,
            quantity=1,
            unit="losses",
            description=f"Loss on killmail {loss.killmail_id}",
            reference_type="EveCharacterKillmail",
            reference_id=ref_id,
        )


# ---------------------------------------------------------------------------
# Freight
# ---------------------------------------------------------------------------


def _sync_freight(tribe_group: TribeGroup):

    committed = {
        c.character_id: (c, u)
        for c, u in _committed_characters_for_group(tribe_group)
    }
    if not committed:
        return

    character_ids = set(committed.keys())
    contracts = EveCharacterContract.objects.filter(
        acceptor_id__in=character_ids,
        type="courier",
        status="finished",
    )

    for contract in contracts:
        character, user = committed[contract.acceptor_id]
        volume = float(contract.volume) if contract.volume else 0.0
        ref_id = str(contract.contract_id)
        _create_activity(
            tribe_group=tribe_group,
            user=user,
            character=character,
            activity_type=TribeActivity.ACTIVITY_FREIGHT,
            quantity=volume,
            unit="m3",
            description=f"Courier contract {contract.contract_id}",
            reference_type="EveCharacterContract",
            reference_id=ref_id,
        )


# ---------------------------------------------------------------------------
# Mining
# ---------------------------------------------------------------------------


def _sync_mining(tribe_group: TribeGroup):

    committed = {
        c.pk: (c, u) for c, u in _committed_characters_for_group(tribe_group)
    }
    if not committed:
        return

    entries = EveCharacterMiningEntry.objects.filter(
        character__pk__in=committed.keys()
    ).select_related("character", "eve_type")

    for entry in entries:
        character, user = committed[entry.character_id]
        ref_id = f"{entry.character_id}:{entry.date}:{entry.eve_type_id}"
        _create_activity(
            tribe_group=tribe_group,
            user=user,
            character=character,
            activity_type=TribeActivity.ACTIVITY_MINING,
            quantity=float(entry.quantity),
            unit="units",
            description=f"Mining: {entry.eve_type} on {entry.date}",
            reference_type="EveCharacterMiningEntry",
            reference_id=ref_id,
        )


# ---------------------------------------------------------------------------
# Industry
# ---------------------------------------------------------------------------


def _sync_industry(tribe_group: TribeGroup):

    blueprint_type_ids = set(tribe_group.blueprint_type_ids or [])
    if not blueprint_type_ids:
        return

    committed = {
        c.pk: (c, u) for c, u in _committed_characters_for_group(tribe_group)
    }
    if not committed:
        return

    jobs = EveCharacterIndustryJob.objects.filter(
        character__pk__in=committed.keys(),
        activity_id=1,  # Manufacturing
        status="delivered",
        blueprint_type_id__in=blueprint_type_ids,
    )

    for job in jobs:
        character, user = committed[job.character_id]
        cost = float(job.cost) if job.cost else 0.0
        ref_id = str(job.job_id)
        _create_activity(
            tribe_group=tribe_group,
            user=user,
            character=character,
            activity_type=TribeActivity.ACTIVITY_INDUSTRY,
            quantity=cost,
            unit="ISK",
            description=f"Industry job {job.job_id} (blueprint {job.blueprint_type_id})",
            reference_type="EveCharacterIndustryJob",
            reference_id=ref_id,
        )


# ---------------------------------------------------------------------------
# Main activity sync task
# ---------------------------------------------------------------------------


@app.task()
def sync_tribe_activities():
    """
    Periodic task. For each active TribeGroup, ingest new TribeActivity rows
    from ESI-derived data (fleet participation, kills, losses, freight, mining,
    industry). Uses reference_id + reference_type to prevent double-ingestion.
    Manual activities (content, custom, doctrine updates) are not ingested here.
    """
    groups = TribeGroup.objects.filter(is_active=True).select_related("tribe")
    for tribe_group in groups:
        try:
            logger.info("Syncing activities for TribeGroup: %s", tribe_group)

            if tribe_group.ship_type_ids:
                _sync_fleet_participation(tribe_group)
                _sync_kills(tribe_group)
                _sync_losses(tribe_group)

            _sync_freight(tribe_group)
            _sync_mining(tribe_group)

            if tribe_group.blueprint_type_ids:
                _sync_industry(tribe_group)

        except Exception as exc:  # pylint: disable=broad-except
            logger.error(
                "Error syncing activities for TribeGroup %s: %s",
                tribe_group,
                exc,
            )


# ---------------------------------------------------------------------------
# Discord reminder task
# ---------------------------------------------------------------------------


def _discord_mention(user) -> str | None:
    """Return a Discord mention string for a user, or None if unavailable."""
    try:
        return f"<@{user.discord_user.id}>"
    except Exception:  # pylint: disable=broad-except
        return None


def _build_reminder_message(tribe_group, memberships: list) -> str:
    """Build the Discord reminder message for a tribe group's pending applications."""
    lines = ["**Pending Tribe Membership Applications**"]
    for m in memberships:
        mention = _discord_mention(m.user)
        if mention:
            lines.append(f"- {mention} → {tribe_group.name}")
        else:
            lines.append(f"- {m.user.username} → {tribe_group.name}")
    lines.append("\nPlease review applications in the admin panel.")

    mentions = []
    if tribe_group.chief:
        chief_mention = _discord_mention(tribe_group.chief)
        if chief_mention:
            mentions.append(chief_mention)
    for elder in tribe_group.elders.all():
        elder_mention = _discord_mention(elder)
        if elder_mention:
            mentions.append(elder_mention)
    if mentions:
        lines.append(" ".join(mentions))

    return "\n".join(lines)


def _send_group_reminder(tribe_group, memberships: list) -> None:
    """Send a pending-application reminder for one tribe group."""
    channel_id = (
        tribe_group.discord_channel_id or tribe_group.tribe.discord_channel_id
    )
    if not channel_id:
        logger.info(
            "TribeGroup %s has no Discord channel configured", tribe_group
        )
        return
    message = _build_reminder_message(tribe_group, memberships)
    try:
        discord.create_message(channel_id, message)
    except Exception as exc:  # pylint: disable=broad-except
        logger.error(
            "Failed to send reminder to Discord channel %s: %s",
            channel_id,
            exc,
        )


@app.task()
def create_tribe_membership_reminders():
    """
    Post Discord reminders to tribe/group channels for any pending
    TribeGroupMembership applications so chiefs and elders can action them.
    """
    pending = (
        TribeGroupMembership.objects.filter(
            status=TribeGroupMembership.STATUS_PENDING
        )
        .select_related("tribe_group__tribe", "tribe_group", "user")
        .prefetch_related("tribe_group__elders")
    )

    by_group: dict = defaultdict(list)
    for membership in pending:
        by_group[membership.tribe_group].append(membership)

    for tribe_group, memberships in by_group.items():
        _send_group_reminder(tribe_group, memberships)


# ---------------------------------------------------------------------------
# Permission cleanup task
# ---------------------------------------------------------------------------


@app.task()
def remove_tribe_members_without_permission():
    """
    Remove users from all TribeGroups if they no longer have the base
    'tribes.add_tribegroupmembership' permission (e.g. they left the alliance).

    Sets status to 'removed' and records left_at, which triggers the
    post_save signal to remove the user from the auth.Group.
    """
    active_memberships = TribeGroupMembership.objects.filter(
        status=TribeGroupMembership.STATUS_APPROVED
    ).select_related("user", "tribe_group__tribe")

    for membership in active_memberships:
        user = membership.user
        try:
            if not user.has_perm("tribes.add_tribegroupmembership"):
                logger.info(
                    "User %s lacks tribes permission; removing from %s",
                    user,
                    membership.tribe_group,
                )
                membership.status = TribeGroupMembership.STATUS_REMOVED
                membership.left_at = timezone.now()
                membership.save(update_fields=["status", "left_at"])
        except Exception as exc:  # pylint: disable=broad-except
            logger.error(
                "Error checking permission for user %s in group %s: %s",
                user,
                membership.tribe_group,
                exc,
            )
