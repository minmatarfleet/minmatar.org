"""Industry Django signals."""

from __future__ import annotations

import logging

from django.db.models.signals import m2m_changed, post_save, pre_delete
from django.dispatch import receiver

from industry.models import IndustryLoyaltyPointMarketOrder, IndustryOrder

logger = logging.getLogger(__name__)


@receiver(m2m_changed, sender=IndustryOrder.tribe_groups.through)
def notify_when_order_tribe_groups_added(
    sender, instance, action, pk_set, **kwargs
):
    """
    When an order is designated to tribe groups (typically via admin), notify
    active members. Idempotent with the create-time emit so prior recipients
    are not re-pinged.
    """
    if action != "post_add" or not pk_set:
        return
    if not isinstance(instance, IndustryOrder):
        return
    if instance.fulfilled_at is not None:
        return

    creator_user_id = None
    try:
        character = instance.character
        creator_user_id = character.user_id if character else None
    except Exception:  # noqa: BLE001 — never fail M2M save on notify
        logger.exception(
            "Could not resolve order %s owner for tribe-group notify",
            instance.pk,
        )

    try:
        # Deferred import: industry.tasks → helpers → … → signals.
        from industry.tasks import (  # pylint: disable=import-outside-toplevel
            emit_order_created_notification,
        )

        emit_order_created_notification.delay(instance.pk, creator_user_id)
    except Exception:  # noqa: BLE001 — never fail M2M save on notify
        logger.exception(
            "Failed to enqueue new-order notification after tribe_groups "
            "change on order %s",
            instance.pk,
        )


def _close_market_order_discord_thread(thread_id: int | None) -> None:
    if not thread_id:
        return
    from industry.tasks import (  # pylint: disable=import-outside-toplevel
        close_lp_buyback_discord_thread_task,
    )

    close_lp_buyback_discord_thread_task.delay(int(thread_id))


@receiver(
    pre_delete,
    sender=IndustryLoyaltyPointMarketOrder,
    dispatch_uid="lp_buyback_order_pre_delete_close_thread",
)
def close_lp_buyback_thread_on_order_delete(sender, instance, **kwargs):
    _close_market_order_discord_thread(instance.discord_thread_id)


@receiver(
    post_save,
    sender=IndustryLoyaltyPointMarketOrder,
    dispatch_uid="lp_buyback_order_post_save_close_thread",
)
def close_lp_buyback_thread_on_order_cancel(
    sender, instance, created, **kwargs
):
    if created:
        return
    if instance.status != IndustryLoyaltyPointMarketOrder.Status.CANCELLED:
        return
    update_fields = kwargs.get("update_fields")
    if update_fields is not None and "status" not in update_fields:
        return
    _close_market_order_discord_thread(instance.discord_thread_id)
