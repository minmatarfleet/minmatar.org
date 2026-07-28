"""Channel adapters: web push, Discord DM, Eve mail."""

from __future__ import annotations

import json
import logging
from typing import Any

from django.conf import settings
from ratelimit import RateLimitException

from discord.client import DiscordClient
from discord.models import DiscordUser
from eveonline.client import EsiClient
from eveonline.helpers.characters import user_primary_character
from notifications.models import NotificationChannel
from notifications.rate_limit import acquire
from subscriptions.models import UserSubscription

try:
    from pywebpush import WebPushException, webpush
except ImportError:  # pragma: no cover - optional until Pipfile install
    WebPushException = Exception  # type: ignore[misc, assignment]
    webpush = None

logger = logging.getLogger(__name__)


class ChannelSendError(Exception):
    """Transient or permanent channel failure."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = True,
        retry_after: float | None = None,
    ):
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after


class ChannelSkip(Exception):
    """Prerequisite missing; mark delivery skipped (not failed)."""


def send_channel(channel: str, user, payload: dict[str, Any]) -> None:
    if channel == NotificationChannel.WEB:
        _send_web(user, payload)
    elif channel == NotificationChannel.DISCORD:
        _send_discord(user, payload)
    elif channel == NotificationChannel.EVE_MAIL:
        _send_eve_mail(user, payload)
    else:
        raise ChannelSendError(f"Unknown channel: {channel}", retryable=False)


def _send_web(user, payload: dict[str, Any]) -> None:
    if webpush is None:
        raise ChannelSendError("pywebpush is not installed", retryable=False)

    vapid_private = getattr(settings, "VAPID_PRIVATE_KEY", "") or ""
    vapid_claims = {
        "sub": getattr(settings, "VAPID_CONTACT", "")
        or "mailto:admin@minmatar.org"
    }
    if not vapid_private:
        raise ChannelSkip("VAPID_PRIVATE_KEY not configured")

    subs = list(UserSubscription.objects.filter(user=user))
    if not subs:
        raise ChannelSkip("No web push subscription")

    body = {
        "title": payload.get("title") or "Minmatar Fleet",
        "body": payload.get("body") or "",
        "icon": payload.get("icon") or "",
        "url": payload.get("url") or "",
    }
    data = json.dumps(body)
    last_error = None
    sent_any = False
    for sub in subs:
        try:
            subscription_info = json.loads(sub.subscription)
        except json.JSONDecodeError:
            logger.warning("Invalid subscription JSON id=%s", sub.id)
            sub.delete()
            continue
        try:
            webpush(
                subscription_info=subscription_info,
                data=data,
                vapid_private_key=vapid_private,
                vapid_claims=vapid_claims,
            )
            sent_any = True
        except WebPushException as exc:
            status = getattr(
                getattr(exc, "response", None), "status_code", None
            )
            if status == 410:
                sub.delete()
                continue
            last_error = exc
            logger.warning(
                "Web push failed for subscription %s: %s", sub.id, exc
            )
    if not sent_any:
        if last_error:
            raise ChannelSendError(
                str(last_error), retryable=True
            ) from last_error
        raise ChannelSkip("No valid web push subscriptions")


def _send_discord(user, payload: dict[str, Any]) -> None:
    discord_user = DiscordUser.objects.filter(user_id=user.id).first()
    if not discord_user:
        raise ChannelSkip("No Discord link")

    rate = float(
        getattr(settings, "NOTIFICATIONS_DISCORD_DM_RATE_PER_SECOND", 2.0)
    )
    allowed, retry_after = acquire(
        "discord_dm",
        rate_per_second=rate,
        capacity=max(rate * 2, 2),
        tokens=2.0,  # open DM channel + send
    )
    if not allowed:
        raise ChannelSendError(
            "Discord DM rate limited (local bucket)",
            retryable=True,
            retry_after=max(retry_after, 1.0),
        )

    message = payload.get("discord_message") or payload.get("body") or ""
    if not message:
        raise ChannelSendError("Empty Discord message", retryable=False)

    try:
        DiscordClient().send_dm(str(discord_user.id), message=message)
    except RateLimitException as exc:
        raise ChannelSendError(
            "Discord API rate limited",
            retryable=True,
            retry_after=5.0,
        ) from exc
    except Exception as exc:
        raise ChannelSendError(str(exc), retryable=True) from exc


def _send_eve_mail(user, payload: dict[str, Any]) -> None:
    primary = user_primary_character(user)
    if not primary:
        raise ChannelSkip("No primary character")

    rate = float(
        getattr(settings, "NOTIFICATIONS_EVE_MAIL_RATE_PER_SECOND", 0.5)
    )
    allowed, retry_after = acquire(
        "eve_mail",
        rate_per_second=rate,
        capacity=max(rate * 2, 1),
        tokens=1.0,
    )
    if not allowed:
        raise ChannelSendError(
            "Eve mail rate limited (local bucket)",
            retryable=True,
            retry_after=max(retry_after, 2.0),
        )

    subject = (
        payload.get("subject") or payload.get("title") or "Minmatar Fleet"
    )
    body = payload.get("eve_mail_body") or payload.get("body") or ""
    if not body:
        raise ChannelSendError("Empty Eve mail body", retryable=False)

    mail_character_id = int(
        getattr(settings, "NOTIFICATIONS_EVE_MAIL_CHARACTER_ID", 634915984)
    )
    mail = {
        "subject": subject,
        "body": body,
        "recipients": [
            {
                "recipient_id": primary.character_id,
                "recipient_type": "character",
            }
        ],
    }
    response = EsiClient(mail_character_id).send_evemail(mail)
    if not response.success():
        raise ChannelSendError(
            f"Eve mail ESI error {response.response_code}",
            retryable=True,
        )
    try:
        response.results()
    except Exception as exc:
        raise ChannelSendError(str(exc), retryable=True) from exc
