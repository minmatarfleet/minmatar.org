"""Celery workers for notification delivery."""

from __future__ import annotations

import logging
from typing import Any

from django.utils import timezone

from app.celery import app
from notifications.channels import (
    LOCAL_BUCKET_DEADLINE_SECONDS,
    LOCAL_BUCKET_ERRORS,
    ChannelSendError,
    ChannelSkip,
    send_channel,
)
from notifications.models import (
    NotificationDelivery,
    NotificationDeliveryStatus,
)

logger = logging.getLogger(__name__)


def _mark_delivery_sent(
    delivery: NotificationDelivery, meta: dict[str, Any] | None
) -> str:
    """Persist SENT (or keep READ) after a successful channel send."""
    channel_id = ""
    message_id = ""
    if isinstance(meta, dict):
        channel_id = str(meta.get("discord_channel_id") or "")
        message_id = str(meta.get("discord_message_id") or "")

    now = timezone.now()
    values = {
        "status": NotificationDeliveryStatus.SENT,
        "error": "",
        "sent_at": now,
        "updated_at": now,
    }
    if channel_id:
        values["discord_channel_id"] = channel_id
    if message_id:
        values["discord_message_id"] = message_id

    # Atomic vs Mark as read: never overwrite READ.
    updated = (
        NotificationDelivery.objects.filter(pk=delivery.pk)
        .exclude(status=NotificationDeliveryStatus.READ)
        .update(**values)
    )
    if updated == 0:
        id_values = {"updated_at": now}
        if channel_id:
            id_values["discord_channel_id"] = channel_id
        if message_id:
            id_values["discord_message_id"] = message_id
        if len(id_values) > 1:
            NotificationDelivery.objects.filter(pk=delivery.pk).update(
                **id_values
            )
        return "sent_already_read"
    return "sent"


def _is_local_bucket(exc: ChannelSendError) -> bool:
    return str(exc) in LOCAL_BUCKET_ERRORS


def _should_retry(self, delivery, exc: ChannelSendError) -> bool:
    if not exc.retryable:
        return False
    if _is_local_bucket(exc):
        age = (timezone.now() - delivery.created_at).total_seconds()
        return age < LOCAL_BUCKET_DEADLINE_SECONDS
    return self.request.retries < self.max_retries


def _handle_send_error(self, delivery, exc: ChannelSendError) -> str:
    if _should_retry(self, delivery, exc):
        delivery.error = str(exc)
        delivery.save(update_fields=["error", "updated_at"])
        countdown = int(exc.retry_after or (2**self.request.retries))
        retry_kwargs = {"exc": exc, "countdown": max(countdown, 1)}
        # Bucket waits must not consume the 8-try failure budget. Allow
        # exactly one more Celery retry; the deadline above is the cap.
        if _is_local_bucket(exc):
            retry_kwargs["max_retries"] = self.request.retries + 1
        raise self.retry(**retry_kwargs)
    delivery.status = NotificationDeliveryStatus.FAILED
    delivery.error = str(exc)
    delivery.save(update_fields=["status", "error", "updated_at"])
    return "failed"


@app.task(
    bind=True,
    max_retries=8,
    autoretry_for=(),
    rate_limit="5/s",
)
def deliver_notification(self, delivery_id: int) -> str:
    try:
        delivery = NotificationDelivery.objects.select_related("user").get(
            pk=delivery_id
        )
    except NotificationDelivery.DoesNotExist:
        logger.warning("Delivery %s not found", delivery_id)
        return "missing"

    if delivery.status in (
        NotificationDeliveryStatus.SENT,
        NotificationDeliveryStatus.READ,
    ):
        return "already_sent"

    delivery.attempts += 1
    delivery.save(update_fields=["attempts", "updated_at"])

    try:
        meta = send_channel(
            delivery.channel,
            delivery.user,
            delivery.payload or {},
            delivery_id=delivery.id,
        )
    except ChannelSkip as exc:
        delivery.status = NotificationDeliveryStatus.SKIPPED
        delivery.error = str(exc)
        delivery.save(update_fields=["status", "error", "updated_at"])
        return "skipped"
    except ChannelSendError as exc:
        return _handle_send_error(self, delivery, exc)
    except Exception as exc:
        logger.exception("Unexpected delivery failure %s", delivery_id)
        if self.request.retries < self.max_retries:
            delivery.error = str(exc)
            delivery.save(update_fields=["error", "updated_at"])
            raise self.retry(exc=exc, countdown=2**self.request.retries)
        delivery.status = NotificationDeliveryStatus.FAILED
        delivery.error = str(exc)
        delivery.save(update_fields=["status", "error", "updated_at"])
        return "failed"

    return _mark_delivery_sent(delivery, meta)
