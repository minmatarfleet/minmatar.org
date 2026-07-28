"""Public notify API: resolve prefs, create deliveries, enqueue workers."""

from __future__ import annotations

import logging
from collections.abc import Iterable

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from notifications.models import (
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationPreference,
)
from notifications.registry import NotificationType, all_types, get_type
from notifications.tasks import deliver_notification

logger = logging.getLogger(__name__)
User = get_user_model()


def preference_enabled(
    user, notification_type: NotificationType, channel: str
) -> bool:
    pref = NotificationPreference.objects.filter(
        user=user,
        notification_type=notification_type.key,
        channel=channel,
    ).first()
    if pref is None:
        return notification_type.default_enabled(channel)
    return pref.enabled


def effective_preferences(user) -> dict[str, dict[str, bool]]:
    """Map type_key -> channel -> enabled for all registered types."""
    stored = {
        (p.notification_type, p.channel): p.enabled
        for p in NotificationPreference.objects.filter(user=user)
    }
    out: dict[str, dict[str, bool]] = {}
    for ntype in all_types():
        channels = {}
        for channel in ntype.allowed_channels():
            key = (ntype.key, channel)
            if key in stored:
                channels[channel] = stored[key]
            else:
                channels[channel] = ntype.default_enabled(channel)
        out[ntype.key] = channels
    return out


def notify_user(
    user,
    type_key: str,
    context: dict | None = None,
    *,
    idempotency_key: str | None = None,
) -> list[NotificationDelivery]:
    return notify_users(
        [user], type_key, context or {}, idempotency_key=idempotency_key
    )


def notify_users(
    users: Iterable,
    type_key: str,
    context: dict | None = None,
    *,
    idempotency_key: str | None = None,
) -> list[NotificationDelivery]:
    """
    Create pending deliveries for each user × enabled channel and enqueue send.

    When idempotency_key is set, duplicate (key, channel) rows are skipped
    (unique constraint). Per-user keys should include user id if fan-out.
    """
    ntype = get_type(type_key)
    context = context or {}
    payload_base = _render_payload(ntype, context)
    created: list[NotificationDelivery] = []

    # Materialize users (may be QuerySet)
    user_list = list(users)
    if not user_list:
        return created

    for user in user_list:
        if user is None:
            continue
        for channel in ntype.allowed_channels():
            if not preference_enabled(user, ntype, channel):
                continue
            if idempotency_key:
                # Fan-out: include user so each recipient can be notified once.
                store_key = f"{idempotency_key}:u{user.id}"
            else:
                store_key = None

            if (
                store_key
                and NotificationDelivery.objects.filter(
                    idempotency_key=store_key, channel=channel
                ).exists()
            ):
                continue

            try:
                with transaction.atomic():
                    delivery = NotificationDelivery.objects.create(
                        user=user,
                        notification_type=type_key,
                        channel=channel,
                        payload=payload_base,
                        status=NotificationDeliveryStatus.PENDING,
                        idempotency_key=store_key,
                    )
            except IntegrityError:
                logger.info(
                    "Skipping duplicate delivery %s %s",
                    store_key,
                    channel,
                )
                continue

            created.append(delivery)
            deliver_notification.delay(delivery.id)

    return created


def _render_payload(ntype: NotificationType, context: dict) -> dict:
    if ntype.render is None:
        return dict(context)
    rendered = ntype.render(context)
    if not isinstance(rendered, dict):
        raise TypeError(
            f"Renderer for {ntype.key} must return a dict, got {type(rendered)}"
        )
    return rendered
