import logging

from django.db import transaction
from django.db.models import signals
from django.dispatch import receiver

from eveonline.models import EveCharacter
from fleets.models import EveFleet, EveFleetShipVolunteer
from fleets.tasks import queue_fleet_schedule_refresh

logger = logging.getLogger(__name__)


def fleet_on_schedule_message(fleet: EveFleet) -> bool:
    """Whether this fleet would appear in the #schedule Discord message.

    Private fleets never do. Tribe group fleets only do when open and
    ``on_schedule``. Alliance fleets need an audience that posts to schedule.
    """
    if getattr(fleet, "invite_only", False):
        return False
    if getattr(fleet, "status", None) == "cancelled":
        return False
    if fleet.host_group_id:
        return bool(fleet.open_to_alliance and fleet.on_schedule)
    audience = getattr(fleet, "audience", None)
    if audience is None:
        return False
    return bool(audience.add_to_schedule)


@receiver(
    signals.pre_save,
    sender=EveFleet,
    dispatch_uid="fleet_schedule_dirty_on_save",
)
def fleet_schedule_dirty_on_save(sender, instance, **kwargs):
    """Refresh when the fleet is on the schedule, or when it just left it."""
    after = fleet_on_schedule_message(instance)
    before = False
    if instance.pk:
        old = (
            EveFleet.objects.filter(pk=instance.pk)
            .select_related("audience")
            .first()
        )
        if old is not None:
            before = fleet_on_schedule_message(old)
    instance.schedule_refresh_needed = before or after


@receiver(
    signals.post_save,
    sender=EveFleet,
    dispatch_uid="update_fleet_schedule_on_save",
)
def update_fleet_schedule_on_save(sender, instance, created, **kwargs):
    # pre_save sets schedule_refresh_needed when both the old and new row are
    # known; fall back for direct calls (tests) and for creates that skipped it.
    if hasattr(instance, "schedule_refresh_needed"):
        should_refresh = bool(instance.schedule_refresh_needed)
    else:
        should_refresh = fleet_on_schedule_message(instance)
    if not should_refresh:
        return
    queue_fleet_schedule_refresh()


@receiver(signals.post_delete, sender=EveFleet)
def update_fleet_schedule_on_delete(sender, instance, **kwargs):
    if not fleet_on_schedule_message(instance):
        return
    queue_fleet_schedule_refresh()


# --- Private fleets (docs/fleets/private-fleets.md) ------------------------


@receiver(
    signals.post_save,
    sender=EveFleet,
    dispatch_uid="private_fleet_thread_on_save",
)
def private_fleet_thread_on_save(sender, instance, created, **kwargs):
    """Open the coordination thread for a new private fleet, and close it
    and edit the invite DMs when one is cancelled. A standard fleet's
    invite DMs are edited when it's cancelled too."""
    if not instance.invite_only:
        if instance.status == "cancelled" and instance.invites.exists():
            # pylint: disable=import-outside-toplevel
            from discord.outbox import on_commit_enqueue
            from fleets.tasks import update_private_fleet_dms

            on_commit_enqueue(
                update_private_fleet_dms,
                (instance.id,),
                context=f"fleet {instance.id} cancelled DMs",
            )
        return
    # pylint: disable=import-outside-toplevel
    from discord.outbox import on_commit_enqueue
    from fleets.tasks import (
        close_private_fleet_thread,
        ensure_private_fleet_thread,
        update_private_fleet_dms,
    )

    if instance.status == "cancelled":
        on_commit_enqueue(
            update_private_fleet_dms,
            (instance.id,),
            context=f"fleet {instance.id} cancelled DMs",
        )
        on_commit_enqueue(
            close_private_fleet_thread,
            (instance.id,),
            context=f"fleet {instance.id} cancelled thread",
        )
        return
    if not instance.discord_thread_id and instance.status == "pending":
        on_commit_enqueue(
            ensure_private_fleet_thread,
            (instance.id,),
            context=f"fleet {instance.id} private thread",
        )


@receiver(
    signals.post_delete,
    sender=EveFleet,
    dispatch_uid="private_fleet_thread_on_delete",
)
def private_fleet_thread_on_delete(sender, instance, **kwargs):
    """A deleted private fleet's thread is archived; the fleet row is gone,
    so this closes it by id."""
    if not instance.invite_only or not instance.discord_thread_id:
        return
    # pylint: disable=import-outside-toplevel
    from discord.client import DiscordClient

    thread_id = instance.discord_thread_id

    def _close():
        try:
            DiscordClient().close_thread(thread_id)
        except Exception:  # pylint: disable=broad-except
            logger.warning("Could not close thread %s", thread_id)

    transaction.on_commit(_close)


def _volunteer_owner_changed(instance) -> None:
    fleet = getattr(instance, "eve_fleet", None)
    if fleet is None or not fleet.invites.exists():
        return
    character = (
        EveCharacter.objects.filter(character_id=instance.character_id)
        .only("user_id")
        .first()
    )
    if character is None or not character.user_id:
        return
    # pylint: disable=import-outside-toplevel
    from fleets.helpers.private_fleets import sync_answer_from_ships

    sync_answer_from_ships(fleet, character.user_id)


@receiver(
    signals.post_save,
    sender=EveFleetShipVolunteer,
    dispatch_uid="private_fleet_answer_on_volunteer_save",
)
def private_fleet_answer_on_volunteer_save(sender, instance, **kwargs):
    """Picking a ship on a fleet you were invited to is saying I'm in."""
    _volunteer_owner_changed(instance)


@receiver(
    signals.post_delete,
    sender=EveFleetShipVolunteer,
    dispatch_uid="private_fleet_answer_on_volunteer_delete",
)
def private_fleet_answer_on_volunteer_delete(sender, instance, **kwargs):
    _volunteer_owner_changed(instance)
