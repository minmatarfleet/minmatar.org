"""Celery workers for notification delivery."""

from __future__ import annotations

import logging

from django.utils import timezone

from app.celery import app
from notifications.channels import ChannelSendError, ChannelSkip, send_channel
from notifications.models import (
    NotificationDelivery,
    NotificationDeliveryStatus,
)

logger = logging.getLogger(__name__)


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

    if delivery.status == NotificationDeliveryStatus.SENT:
        return "already_sent"

    delivery.attempts += 1
    delivery.save(update_fields=["attempts", "updated_at"])

    try:
        send_channel(delivery.channel, delivery.user, delivery.payload or {})
    except ChannelSkip as exc:
        delivery.status = NotificationDeliveryStatus.SKIPPED
        delivery.error = str(exc)
        delivery.save(update_fields=["status", "error", "updated_at"])
        return "skipped"
    except ChannelSendError as exc:
        if exc.retryable and self.request.retries < self.max_retries:
            delivery.error = str(exc)
            delivery.save(update_fields=["error", "updated_at"])
            countdown = int(exc.retry_after or (2**self.request.retries))
            raise self.retry(exc=exc, countdown=max(countdown, 1))
        delivery.status = NotificationDeliveryStatus.FAILED
        delivery.error = str(exc)
        delivery.save(update_fields=["status", "error", "updated_at"])
        return "failed"
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

    delivery.status = NotificationDeliveryStatus.SENT
    delivery.error = ""
    delivery.sent_at = timezone.now()
    delivery.save(update_fields=["status", "error", "sent_at", "updated_at"])
    return "sent"
