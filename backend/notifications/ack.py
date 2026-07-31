"""Acknowledge / mark-as-read helpers for notification deliveries."""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser
from django.utils import timezone

from discord.models import DiscordUser
from notifications.models import (
    NotificationDelivery,
    NotificationDeliveryStatus,
)


class AckError(Exception):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _mark_read(delivery: NotificationDelivery) -> NotificationDelivery:
    if delivery.status == NotificationDeliveryStatus.READ:
        return delivery

    if delivery.status not in (
        NotificationDeliveryStatus.SENT,
        NotificationDeliveryStatus.PENDING,
    ):
        raise AckError(
            f"Cannot ack delivery in status {delivery.status}",
            status_code=400,
        )

    delivery.status = NotificationDeliveryStatus.READ
    delivery.read_at = timezone.now()
    delivery.save(update_fields=["status", "read_at", "updated_at"])
    return delivery


def ack_delivery_for_requester(
    delivery_id: int,
    *,
    requester: AbstractBaseUser,
    discord_user_id: int,
) -> NotificationDelivery:
    """
    Mark a Discord delivery as read.

    Allowed when:
    - requester owns the delivery, and discord_user_id is their Discord link, or
    - requester is staff/superuser (bot service token) and discord_user_id
      maps to the delivery owner.
    """
    try:
        delivery = NotificationDelivery.objects.select_related("user").get(
            pk=delivery_id
        )
    except NotificationDelivery.DoesNotExist as exc:
        raise AckError("Delivery not found", status_code=404) from exc

    discord_user = DiscordUser.objects.filter(id=discord_user_id).first()
    if not discord_user or discord_user.user_id != delivery.user_id:
        raise AckError("Not your notification", status_code=403)

    is_owner = requester.id == delivery.user_id
    is_service = bool(
        getattr(requester, "is_staff", False)
        or getattr(requester, "is_superuser", False)
    )
    if not is_owner and not is_service:
        raise AckError("Not your notification", status_code=403)

    if is_owner:
        linked = DiscordUser.objects.filter(user_id=requester.id).first()
        if not linked or int(linked.id) != int(discord_user_id):
            raise AckError("Not your notification", status_code=403)

    return _mark_read(delivery)


def ack_delivery_for_discord_user(
    delivery_id: int, discord_user_id: int
) -> NotificationDelivery:
    """
    Mark a Discord delivery as read if the Discord user owns it.

    Prefer ack_delivery_for_requester for API calls (auth-aware).
    Idempotent when already read.
    """
    try:
        delivery = NotificationDelivery.objects.select_related("user").get(
            pk=delivery_id
        )
    except NotificationDelivery.DoesNotExist as exc:
        raise AckError("Delivery not found", status_code=404) from exc

    discord_user = DiscordUser.objects.filter(id=discord_user_id).first()
    if not discord_user or discord_user.user_id != delivery.user_id:
        raise AckError("Not your notification", status_code=403)

    return _mark_read(delivery)
