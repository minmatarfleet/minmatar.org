import logging

from django.db import transaction
from django.db.models import signals
from django.dispatch import receiver

from eveonline.models import EveCharacter
from fleets.models import EveFleet, EveFleetShipVolunteer
from fleets.tasks import queue_fleet_schedule_refresh

logger = logging.getLogger(__name__)


@receiver(
    signals.post_save,
    sender=EveFleet,
    dispatch_uid="update_fleet_schedule_on_save",
)
def update_fleet_schedule_on_save(sender, instance, created, **kwargs):
    if instance.audience and not instance.audience.add_to_schedule:
        return
    queue_fleet_schedule_refresh()


@receiver(signals.post_delete, sender=EveFleet)
def update_fleet_schedule_on_delete(sender, instance, **kwargs):
    queue_fleet_schedule_refresh()


# --- Private fleets (docs/fleets/private-fleets.md) ------------------------


@receiver(
    signals.post_save,
    sender=EveFleet,
    dispatch_uid="private_fleet_thread_on_save",
)
def private_fleet_thread_on_save(sender, instance, created, **kwargs):
    """Open the coordination thread for a new private fleet, and close it
    and edit the invite DMs when one is cancelled."""
    if not instance.invite_only:
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
    if fleet is None or not fleet.invite_only:
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
    """Picking a ship on a private fleet is saying I'm in."""
    _volunteer_owner_changed(instance)


@receiver(
    signals.post_delete,
    sender=EveFleetShipVolunteer,
    dispatch_uid="private_fleet_answer_on_volunteer_delete",
)
def private_fleet_answer_on_volunteer_delete(sender, instance, **kwargs):
    _volunteer_owner_changed(instance)
