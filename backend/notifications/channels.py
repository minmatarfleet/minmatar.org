"""Channel adapters: web push, Discord DM, Eve mail."""

from __future__ import annotations

import json
import logging
from typing import Any

import requests
from django.conf import settings
from ratelimit import RateLimitException

from discord.client import DiscordClient
from discord.models import DiscordUser
from eveonline.client import (
    ERROR_CALLING_ESI,
    EsiClient,
)
from eveonline.helpers.characters import user_primary_character
from notifications.discord_buttons import mark_as_read_components
from notifications.discord_format import discord_embed_from_payload
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


def send_channel(
    channel: str,
    user,
    payload: dict[str, Any],
    *,
    delivery_id: int | None = None,
) -> dict[str, Any] | None:
    """
    Send on the given channel.

    For Discord, returns {"discord_channel_id", "discord_message_id"} when known.
    """
    if channel == NotificationChannel.WEB:
        _send_web(user, payload)
        return None
    if channel == NotificationChannel.DISCORD:
        return _send_discord(user, payload, delivery_id=delivery_id)
    if channel == NotificationChannel.EVE_MAIL:
        _send_eve_mail(user, payload)
        return None
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


def _send_discord(
    user, payload: dict[str, Any], *, delivery_id: int | None = None
) -> dict[str, Any]:
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
    if not message and not payload.get("discord_embed"):
        raise ChannelSendError("Empty Discord message", retryable=False)

    # Prefer an explicit embed; otherwise brand with feature author + body.
    embed = payload.get("discord_embed") or discord_embed_from_payload(payload)
    discord_payload: dict[str, Any] = {"embeds": [embed]}
    if delivery_id is not None:
        discord_payload["components"] = mark_as_read_components(delivery_id)

    try:
        response = DiscordClient().send_dm(
            str(discord_user.id), payload=discord_payload
        )
        data = response.json() if hasattr(response, "json") else response
    except RateLimitException as exc:
        raise ChannelSendError(
            "Discord API rate limited",
            retryable=True,
            retry_after=5.0,
        ) from exc
    except requests.HTTPError as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status == 403:
            # Typically "Cannot send messages to this user" (DMs closed).
            raise ChannelSkip(f"Discord DM forbidden ({status})") from exc
        if status is not None and 400 <= status < 500:
            raise ChannelSendError(
                f"Discord HTTP {status}",
                retryable=False,
            ) from exc
        raise ChannelSendError(str(exc), retryable=True) from exc
    except Exception as exc:
        raise ChannelSendError(str(exc), retryable=True) from exc

    channel_id = str(data.get("channel_id") or "")
    message_id = str(data.get("id") or "")
    return {
        "discord_channel_id": channel_id,
        "discord_message_id": message_id,
    }


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
        code = int(response.response_code)
        # Auth / client / 4xx are permanent; 5xx and transport (906) retry.
        retryable = code >= 500 or code == ERROR_CALLING_ESI or code == 429
        raise ChannelSendError(
            f"Eve mail ESI error {code}",
            retryable=retryable,
        )
    try:
        response.results()
    except Exception as exc:
        raise ChannelSendError(str(exc), retryable=True) from exc
