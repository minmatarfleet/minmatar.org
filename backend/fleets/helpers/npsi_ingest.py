"""Poll NPSI JSON feeds, upsert events, and DM FCs to confirm posting."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone as dt_timezone

import requests
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from discord.client import DiscordClient
from discord.models import DiscordUser
from eveonline.models import EveCharacter
from groups.helpers.feature_access import can_use_feature
from fleets.helpers.npsi_description import sanitize_npsi_description
from fleets.helpers.npsi_discord import notify_dm_payload
from fleets.models import NpsiEventSource, NpsiExternalEvent

logger = logging.getLogger(__name__)

FEED_TIMEOUT_SECONDS = 15


def event_fingerprint(source_id: int, start: datetime, summary: str) -> str:
    start_utc = start.astimezone(dt_timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    raw = f"{source_id}|{start_utc}|{(summary or '').strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def parse_feed_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = parse_datetime(value.replace("Z", "+00:00"))
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, dt_timezone.utc)
    return parsed


def resolve_fc_user(character_name: str) -> User | None:
    if not character_name:
        return None
    character = (
        EveCharacter.objects.filter(character_name=character_name)
        .select_related("user")
        .first()
    )
    if character is None or character.user_id is None:
        return None
    return character.user


def resolve_fc_discord_id(user: User) -> int | None:
    discord_user = DiscordUser.objects.filter(user_id=user.id).first()
    if discord_user is None:
        return None
    return int(discord_user.id)


def poll_npsi_sources(*, force_renotify: bool = False) -> dict:
    stats = {"sources": 0, "upserted": 0, "notified": 0, "skipped": 0}
    sources = NpsiEventSource.objects.filter(enabled=True)
    for source in sources:
        stats["sources"] += 1
        try:
            result = poll_npsi_source(source, force_renotify=force_renotify)
        except Exception:
            logger.exception("NPSI poll failed for source %s", source.name)
            continue
        stats["upserted"] += result["upserted"]
        stats["notified"] += result["notified"]
        stats["skipped"] += result["skipped"]
    return stats


def poll_npsi_source(
    source: NpsiEventSource, *, force_renotify: bool = False
) -> dict:
    stats = {"upserted": 0, "notified": 0, "skipped": 0}
    try:
        response = requests.get(source.feed_url, timeout=FEED_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException:
        logger.warning(
            "NPSI feed %s request failed", source.name, exc_info=True
        )
        return stats
    if not isinstance(payload, list):
        logger.warning("NPSI feed %s did not return a list", source.name)
        return stats

    now = timezone.now()
    for item in payload:
        if not isinstance(item, dict):
            continue
        handled = upsert_feed_item(
            source, item, now=now, force_renotify=force_renotify
        )
        stats["upserted"] += handled["upserted"]
        stats["notified"] += handled["notified"]
        stats["skipped"] += handled["skipped"]
    return stats


def upsert_feed_item(
    source: NpsiEventSource,
    item: dict,
    *,
    now,
    force_renotify: bool = False,
    notify_discord_user_id: int | None = None,
    include_past: bool = False,
    skip_notify: bool = False,
) -> dict:
    stats = {"upserted": 0, "notified": 0, "skipped": 0}
    summary = (item.get("summary") or "").strip() or "NPSI fleet"
    start = parse_feed_datetime(item.get("start"))
    if start is None:
        stats["skipped"] += 1
        return stats
    if start < now and not include_past:
        stats["skipped"] += 1
        return stats

    fingerprint = event_fingerprint(source.id, start, summary)
    character_name = (
        item.get("character_name") or ""
    ).strip() or source.fc_character_name
    description = sanitize_npsi_description(item.get("description"))
    location_text = (item.get("location") or "").strip()
    end = parse_feed_datetime(item.get("end"))

    event, created = NpsiExternalEvent.objects.get_or_create(
        fingerprint=fingerprint,
        defaults={
            "source": source,
            "summary": summary[:255],
            "description": description,
            "location_text": location_text[:255],
            "character_name": character_name[:255],
            "start_time": start,
            "end_time": end,
            "all_day": bool(item.get("allDay")),
            "status": NpsiExternalEvent.Status.SEEN,
        },
    )
    stats["upserted"] += 1
    if not created and event.status != NpsiExternalEvent.Status.CREATED:
        event.summary = summary[:255]
        event.description = description
        event.location_text = location_text[:255]
        event.character_name = character_name[:255]
        event.start_time = start
        event.end_time = end
        event.all_day = bool(item.get("allDay"))
        event.save()

    if event.status == NpsiExternalEvent.Status.CREATED:
        return stats
    if skip_notify:
        if event.status != NpsiExternalEvent.Status.CREATED:
            event.status = NpsiExternalEvent.Status.NOTIFIED
            event.skip_reason = ""
            event.save(update_fields=["status", "skip_reason", "updated_at"])
        return stats
    if (
        event.status == NpsiExternalEvent.Status.NOTIFIED
        and not force_renotify
        and notify_discord_user_id is None
    ):
        return stats

    skip_reason = notify_fc(
        event,
        override_discord_user_id=notify_discord_user_id,
    )
    if skip_reason:
        event.status = NpsiExternalEvent.Status.SKIPPED
        event.skip_reason = skip_reason[:255]
        event.save(update_fields=["status", "skip_reason", "updated_at"])
        stats["skipped"] += 1
        return stats

    event.status = NpsiExternalEvent.Status.NOTIFIED
    event.skip_reason = ""
    event.save(
        update_fields=[
            "status",
            "skip_reason",
            "discord_channel_id",
            "discord_message_id",
            "updated_at",
        ]
    )
    stats["notified"] += 1
    return stats


def notify_fc(
    event: NpsiExternalEvent,
    *,
    override_discord_user_id: int | None = None,
) -> str | None:
    source = event.source
    if source.default_audience_id is None:
        return "No default audience configured"

    fc_user = resolve_fc_user(event.character_name or source.fc_character_name)
    if fc_user is None:
        return "FC character is not linked to a site user"
    if not can_use_feature(fc_user, "fleets.create"):
        return "FC cannot create fleets"

    discord_id = override_discord_user_id or resolve_fc_discord_id(fc_user)
    if discord_id is None:
        return "FC has no Discord link"

    try:
        response = DiscordClient().send_dm(
            str(discord_id), payload=notify_dm_payload(event)
        )
    except Exception as exc:
        logger.warning(
            "NPSI DM failed event=%s discord=%s: %s",
            event.id,
            discord_id,
            exc,
        )
        return "Discord DM failed"

    data = response.json() if hasattr(response, "json") else response
    if isinstance(data, dict):
        channel_id = data.get("channel_id")
        message_id = data.get("id")
        if channel_id:
            event.discord_channel_id = int(channel_id)
        if message_id:
            event.discord_message_id = int(message_id)
    return None
