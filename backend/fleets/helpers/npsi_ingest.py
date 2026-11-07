"""Poll NPSI JSON feeds, upsert events, and DM FCs to confirm posting."""

from __future__ import annotations

import hashlib
import ipaddress
import logging
import socket
from datetime import datetime
from datetime import timezone as dt_timezone
from urllib.parse import urljoin, urlparse

import requests
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from discord.client import DiscordClient
from discord.models import DiscordUser
from eveonline.models import EveCharacter
from fleets.helpers.npsi_description import sanitize_npsi_description
from fleets.helpers.npsi_discord import notify_dm_payload
from fleets.models import NpsiEventSource, NpsiExternalEvent
from groups.helpers.feature_access import can_use_feature

logger = logging.getLogger(__name__)

FEED_TIMEOUT_SECONDS = 15
_FEED_REDIRECTS = 5
_LOCAL_FEED_HOSTS = frozenset({"localhost", "localhost.localdomain"})


def public_feed_url(url: str) -> bool:
    """True for an http(s) URL that is not a loopback, private, or link-local host.

    A name that does not resolve yet is allowed: the poll fails on its own,
    and tests point at names that are not in DNS. A name that resolves to a
    non-public address is rejected.
    """
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme not in ("http", "https") or not host:
        return False
    if parsed.username or parsed.password:
        return False
    if host in _LOCAL_FEED_HOSTS or host.endswith((".local", ".internal")):
        return False
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        return bool(literal.is_global)
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return True
    addresses = []
    for info in infos:
        try:
            addresses.append(ipaddress.ip_address(info[4][0]))
        except ValueError:
            return False
    return bool(addresses) and all(addr.is_global for addr in addresses)


def _fetch_feed(url: str):
    current = url
    for _ in range(_FEED_REDIRECTS):
        if not public_feed_url(current):
            raise requests.RequestException(
                "Feed URL is not a public address."
            )
        response = requests.get(
            current, timeout=FEED_TIMEOUT_SECONDS, allow_redirects=False
        )
        if response.is_redirect is True:
            location = response.headers.get("Location")
            if not location:
                raise requests.RequestException(
                    "Feed redirect had no location."
                )
            current = urljoin(current, location)
            continue
        return response
    raise requests.RequestException("Feed redirected too many times.")


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


def _record_poll(source: NpsiEventSource, error: str = "") -> None:
    now = timezone.now()
    NpsiEventSource.objects.filter(pk=source.pk).update(
        last_polled_at=now,
        last_error=error[:255],
        **({} if error else {"last_success_at": now}),
    )


NOT_A_LIST = "The feed did not return a list of events."


def read_feed(url: str) -> tuple[list | None, str]:
    """Fetch a feed and parse its JSON list: (items, "") or (None, error)."""
    try:
        response = _fetch_feed(url)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("NPSI feed %s request failed", url, exc_info=True)
        return None, f"Feed request failed: {exc}"
    if not isinstance(payload, list):
        logger.warning("NPSI feed %s did not return a list", url)
        return None, NOT_A_LIST
    return payload, ""


def feed_error_kind(error: str) -> str:
    """Sort a stored poll error into a kind the site words in plain language.

    timeout, unreachable, http, not_json, not_list, not_public, or other.
    """
    text = (error or "").lower()
    if not text:
        return ""
    if "timed out" in text or "timeout" in text:
        return "timeout"
    if "not a public address" in text:
        return "not_public"
    if text.startswith(NOT_A_LIST.lower()):
        return "not_list"
    if "client error" in text or "server error" in text:
        return "http"
    if (
        "max retries" in text
        or "failed to resolve" in text
        or "name or service not known" in text
        or "connection refused" in text
        or "connectionerror" in text
    ):
        return "unreachable"
    if "expecting value" in text or "json" in text:
        return "not_json"
    return "other"


TRY_PREVIEW_LIMIT = 5


def try_feed(source: NpsiEventSource) -> dict:
    """Read a source's feed now without storing or sending anything.

    A dry run for the manage screen: no events are written, the source's poll
    columns are left alone, and nobody is messaged on Discord.
    """
    items, error = read_feed(source.feed_url)
    if items is None:
        return {
            "ok": False,
            "error": error[:255],
            "error_kind": feed_error_kind(error),
            "item_count": 0,
            "upcoming_count": 0,
            "upcoming": [],
        }
    now = timezone.now()
    upcoming = []
    for item in items:
        if not isinstance(item, dict):
            continue
        start = parse_feed_datetime(item.get("start"))
        if start is None or start < now:
            continue
        upcoming.append(
            {
                "summary": (
                    (item.get("summary") or "").strip() or "NPSI fleet"
                )[:255],
                "start_time": start,
                "character_name": (
                    (item.get("character_name") or "").strip()
                    or source.fc_character_name
                )[:255],
            }
        )
    upcoming.sort(key=lambda row: row["start_time"])
    return {
        "ok": True,
        "error": "",
        "error_kind": "",
        "item_count": len(items),
        "upcoming_count": len(upcoming),
        "upcoming": upcoming[:TRY_PREVIEW_LIMIT],
    }


def poll_npsi_source(
    source: NpsiEventSource, *, force_renotify: bool = False
) -> dict:
    stats = {"upserted": 0, "notified": 0, "skipped": 0}
    payload, error = read_feed(source.feed_url)
    if payload is None:
        _record_poll(source, error)
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
    _record_poll(source)
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
