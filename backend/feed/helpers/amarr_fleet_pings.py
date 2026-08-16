from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.utils import timezone

from discord.client import DiscordClient
from discord.models import DiscordChannel
from feed.constants import (
    AMARR_FLEET_PING_EDIT_MIN_SECONDS,
    AMARR_FLEET_PING_MAX_AGE_SECONDS,
    AMARR_FLEET_PING_SESSION_SECONDS,
)
from feed.models import FeedAmarrFleetAlert, FeedAmarrFleetPing, FeedEvent
from ratelimit import RateLimitException
from requests.exceptions import HTTPError

logger = logging.getLogger(__name__)

_DISCORD_EDIT_SOFT_FAIL_STATUSES = frozenset({400, 404, 500, 502, 503, 504})


def _is_discord_edit_soft_fail(exc: BaseException) -> bool:
    if not isinstance(exc, HTTPError) or exc.response is None:
        return False
    return exc.response.status_code in _DISCORD_EDIT_SOFT_FAIL_STATUSES


AMARR_FLEET_ALERT_TITLE = "Amarr fleet spotted"
# Matches mobile fleetYellow (#f1d9a0) used for Amarr feed accents.
AMARR_FLEET_ALERT_COLOR = 0xF1D9A0
ZKILL_CHARACTER_URL = "https://zkillboard.com/character/{character_id}/"


def _amarr_fleet_ping_channel_ids() -> list[int]:
    return list(
        DiscordChannel.objects.filter(
            receive_amarr_fleet_pings=True,
            guild__is_active=True,
        ).values_list("channel_id", flat=True)
    )


def _zkill_character_link(character_id: int, name: str) -> str:
    url = ZKILL_CHARACTER_URL.format(character_id=int(character_id))
    return f"[{name}]({url})"


def _system_entry(
    *,
    solar_system_id: int,
    system_name: str,
) -> dict[str, Any]:
    return {
        "solar_system_id": int(solar_system_id),
        "system_name": system_name,
    }


def _append_system(
    systems: list[dict[str, Any]] | None,
    *,
    solar_system_id: int,
    system_name: str,
) -> list[dict[str, Any]]:
    """Extend the sighting chain; refresh tip if still in the same system."""
    entry = _system_entry(
        solar_system_id=solar_system_id,
        system_name=system_name,
    )
    chain = list(systems or [])
    if chain and int(chain[-1]["solar_system_id"]) == int(solar_system_id):
        chain[-1] = entry
        return chain
    chain.append(entry)
    return chain


def _systems_for_alert(alert: FeedAmarrFleetAlert) -> list[dict[str, Any]]:
    if alert.systems:
        return list(alert.systems)
    return [
        _system_entry(
            solar_system_id=int(alert.solar_system_id),
            system_name=alert.system_name,
        )
    ]


def _format_system_line(
    systems: list[dict[str, Any]] | None,
    fallback_name: str,
) -> str:
    names = [
        str(entry["system_name"])
        for entry in systems or []
        if entry.get("system_name")
    ]
    if not names:
        return fallback_name
    return " → ".join(names)


def _roster_links(roster: list[dict[str, Any]] | None) -> str:
    links: list[str] = []
    for entry in roster or []:
        character_id = entry.get("character_id")
        name = entry.get("name")
        if not character_id or not name:
            continue
        links.append(_zkill_character_link(int(character_id), str(name)))
    return ", ".join(links)


def build_amarr_fleet_alert_payload(
    *,
    system_name: str,
    title: str,
    subheader: str,
    preview: str,
    kills: int,
    pilots: int,
    roster: list[dict[str, Any]] | None = None,
    roster_total: int = 0,
    systems: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build Discord payload for an Amarr fleet presence alert."""
    description_lines = [
        f"**System:** {_format_system_line(systems, system_name)}",
        f"**Fleet:** {title}",
    ]
    if subheader:
        description_lines.append(f"**Summary:** {subheader}")
    elif kills or pilots:
        parts: list[str] = []
        if kills:
            parts.append(f"{kills} kills")
        if pilots:
            parts.append(f"{pilots} pilots")
        description_lines.append(f"**Summary:** {' · '.join(parts)}")
    if preview:
        description_lines.append(preview)
    roster_line = _roster_links(roster)
    if roster_line:
        shown = len(roster or [])
        total = max(int(roster_total or 0), shown)
        suffix = f" (+{total - shown} more)" if total > shown else ""
        description_lines.append(f"**Pilots:** {roster_line}{suffix}")

    embed: dict[str, Any] = {
        "type": "rich",
        "title": AMARR_FLEET_ALERT_TITLE,
        "description": "\n".join(description_lines),
        "color": AMARR_FLEET_ALERT_COLOR,
    }
    return {"embeds": [embed]}


def _event_snapshot(event: FeedEvent) -> dict[str, Any]:
    payload = event.payload or {}
    system_id = payload.get("system_id")
    system_name = (
        payload.get("system_name") or event.subheader.split("·")[0].strip()
    )
    if not system_id:
        raise ValueError("Amarr fleet event missing system_id")
    return {
        "solar_system_id": int(system_id),
        "system_name": str(system_name or f"System {system_id}"),
        "title": event.title,
        "subheader": event.subheader or "",
        "preview": event.preview or "",
        "kills": int(payload.get("kills") or 0),
        "pilots": int(payload.get("pilots") or 0),
        "roster": list(payload.get("roster") or []),
        "roster_total": int(payload.get("roster_total") or 0),
        "cluster_key": event.cluster_key or "",
        "is_active": bool(event.is_active),
        "occurred_at": event.occurred_at,
    }


def _is_fresh_fleet(event: FeedEvent) -> bool:
    """True when the fleet tip is recent enough to warrant Discord traffic."""
    if event.occurred_at is None:
        return False
    age_seconds = (timezone.now() - event.occurred_at).total_seconds()
    return age_seconds <= AMARR_FLEET_PING_MAX_AGE_SECONDS


def _active_alert(solar_system_id: int) -> FeedAmarrFleetAlert | None:
    """Find a live Amarr fleet alert for this system within the session TTL."""
    cutoff = timezone.now() - timedelta(
        seconds=AMARR_FLEET_PING_SESSION_SECONDS
    )
    return (
        FeedAmarrFleetAlert.objects.filter(
            last_activity_at__gte=cutoff,
            solar_system_id=int(solar_system_id),
        )
        .order_by("-last_activity_at")
        .first()
    )


def _alert_for_cluster(cluster_key: str) -> FeedAmarrFleetAlert | None:
    """Return the alert previously used for this cluster, if still in session."""
    if not cluster_key:
        return None
    ping = (
        FeedAmarrFleetPing.objects.select_related("alert")
        .filter(cluster_key=cluster_key, alert__isnull=False)
        .first()
    )
    if ping is None or ping.alert is None:
        return None
    cutoff = timezone.now() - timedelta(
        seconds=AMARR_FLEET_PING_SESSION_SECONDS
    )
    if ping.alert.last_activity_at < cutoff:
        return None
    return ping.alert


def _post_alert_messages(
    payload: dict[str, Any],
    *,
    discord_client: DiscordClient,
) -> list[dict[str, int]]:
    messages: list[dict[str, int]] = []
    for channel_id in _amarr_fleet_ping_channel_ids():
        response = discord_client.create_message(
            channel_id=channel_id, payload=payload
        )
        message_id = response.json().get("id")
        if message_id:
            messages.append(
                {
                    "channel_id": int(channel_id),
                    "message_id": int(message_id),
                }
            )
    return messages


def _edit_alert_messages(
    alert: FeedAmarrFleetAlert,
    payload: dict[str, Any],
    *,
    discord_client: DiscordClient,
) -> None:
    for entry in alert.discord_messages or []:
        channel_id = entry.get("channel_id")
        message_id = entry.get("message_id")
        if not channel_id or not message_id:
            continue
        discord_client.update_message(
            channel_id=int(channel_id),
            message_id=int(message_id),
            payload=payload,
        )


def _create_amarr_fleet_alert(
    *,
    snapshot: dict[str, Any],
    discord_client: DiscordClient,
) -> FeedAmarrFleetAlert | None:
    systems = [
        _system_entry(
            solar_system_id=snapshot["solar_system_id"],
            system_name=snapshot["system_name"],
        )
    ]
    discord_payload = build_amarr_fleet_alert_payload(
        system_name=snapshot["system_name"],
        title=snapshot["title"],
        subheader=snapshot["subheader"],
        preview=snapshot["preview"],
        kills=snapshot["kills"],
        pilots=snapshot["pilots"],
        roster=snapshot["roster"],
        roster_total=snapshot["roster_total"],
        systems=systems,
    )
    discord_messages = _post_alert_messages(
        discord_payload, discord_client=discord_client
    )
    if not discord_messages:
        return None
    return FeedAmarrFleetAlert.objects.create(
        solar_system_id=snapshot["solar_system_id"],
        system_name=snapshot["system_name"],
        systems=systems,
        title=snapshot["title"],
        subheader=snapshot["subheader"],
        preview=snapshot["preview"],
        kills=snapshot["kills"],
        pilots=snapshot["pilots"],
        roster=snapshot["roster"],
        roster_total=snapshot["roster_total"],
        cluster_key=snapshot["cluster_key"],
        discord_messages=discord_messages,
        last_activity_at=timezone.now(),
    )


def _alert_content_changed(
    alert: FeedAmarrFleetAlert, snapshot: dict[str, Any]
) -> bool:
    return (
        alert.solar_system_id != snapshot["solar_system_id"]
        or alert.system_name != snapshot["system_name"]
        or alert.title != snapshot["title"]
        or alert.subheader != snapshot["subheader"]
        or alert.preview != snapshot["preview"]
        or alert.kills != snapshot["kills"]
        or alert.pilots != snapshot["pilots"]
        or alert.roster != snapshot["roster"]
        or alert.roster_total != snapshot["roster_total"]
    )


def _should_edit_discord(
    alert: FeedAmarrFleetAlert,
    snapshot: dict[str, Any],
    *,
    now,
) -> bool:
    """Edit Discord when content changed, or after the min edit interval."""
    if _alert_content_changed(alert, snapshot):
        return True
    age = (now - alert.last_activity_at).total_seconds()
    return age >= AMARR_FLEET_PING_EDIT_MIN_SECONDS


def _update_amarr_fleet_alert(
    alert: FeedAmarrFleetAlert,
    *,
    snapshot: dict[str, Any],
    discord_client: DiscordClient,
) -> FeedAmarrFleetAlert:
    now = timezone.now()
    should_edit = _should_edit_discord(alert, snapshot, now=now)
    alert.systems = _append_system(
        _systems_for_alert(alert),
        solar_system_id=snapshot["solar_system_id"],
        system_name=snapshot["system_name"],
    )
    alert.solar_system_id = snapshot["solar_system_id"]
    alert.system_name = snapshot["system_name"]
    alert.title = snapshot["title"]
    alert.subheader = snapshot["subheader"]
    alert.preview = snapshot["preview"]
    alert.kills = snapshot["kills"]
    alert.pilots = snapshot["pilots"]
    alert.roster = snapshot["roster"]
    alert.roster_total = snapshot["roster_total"]
    alert.cluster_key = snapshot["cluster_key"] or alert.cluster_key
    if should_edit:
        alert.last_activity_at = now
        discord_payload = build_amarr_fleet_alert_payload(
            system_name=alert.system_name,
            title=alert.title,
            subheader=alert.subheader,
            preview=alert.preview,
            kills=alert.kills,
            pilots=alert.pilots,
            roster=alert.roster,
            roster_total=alert.roster_total,
            systems=alert.systems,
        )
        _edit_alert_messages(
            alert, discord_payload, discord_client=discord_client
        )
    alert.save(
        update_fields=[
            "solar_system_id",
            "system_name",
            "systems",
            "title",
            "subheader",
            "preview",
            "kills",
            "pilots",
            "roster",
            "roster_total",
            "cluster_key",
            "last_activity_at",
        ]
    )
    return alert


def _record_amarr_fleet_ping(
    *,
    cluster_key: str,
    alert: FeedAmarrFleetAlert,
    solar_system_id: int,
    created: bool,
) -> None:
    if not cluster_key:
        return
    first_message_id = None
    if alert.discord_messages:
        first_message_id = alert.discord_messages[0].get("message_id")
    FeedAmarrFleetPing.objects.update_or_create(
        cluster_key=cluster_key,
        defaults={
            "alert": alert,
            "solar_system_id": solar_system_id,
            "discord_message_id": first_message_id,
        },
    )
    action = "created" if created else "updated"
    logger.info(
        "Amarr fleet alert %s for cluster %s in system %s",
        action,
        cluster_key,
        solar_system_id,
    )


def _is_amarr_fleet_event(event: FeedEvent) -> bool:
    return (
        event.kind == FeedEvent.Kind.FLEET_ACTIVE
        and event.accent == FeedEvent.Accent.AMARR
        and bool(event.cluster_key)
    )


def _upsert_amarr_fleet_alert(
    *,
    snapshot: dict[str, Any],
    existing: FeedAmarrFleetAlert | None,
    discord_client: DiscordClient,
) -> tuple[FeedAmarrFleetAlert | None, bool]:
    """Create or update an alert. Returns (alert, created)."""
    if existing is None:
        alert = _create_amarr_fleet_alert(
            snapshot=snapshot, discord_client=discord_client
        )
        return alert, True
    alert = _update_amarr_fleet_alert(
        existing, snapshot=snapshot, discord_client=discord_client
    )
    return alert, False


def maybe_notify_amarr_fleet(
    event: FeedEvent,
    *,
    discord_client: DiscordClient | None = None,
) -> bool:
    """Create or update a Discord Amarr fleet alert from a feed event.

    Returns True if a Discord message was created or edited, False if skipped.

    Guards against rollup catch-up spam:
    - Only active fleets with a fresh ``occurred_at`` may create new messages.
    - Cluster keys that were already pinged never create a second message;
      they only edit an in-session alert when one still exists.
    """
    if not _amarr_fleet_ping_channel_ids() or not _is_amarr_fleet_event(event):
        return False

    try:
        snapshot = _event_snapshot(event)
    except (TypeError, ValueError):
        logger.exception(
            "Amarr fleet ping skipped: invalid event payload id=%s", event.pk
        )
        return False

    client = discord_client or DiscordClient()
    existing = _alert_for_cluster(snapshot["cluster_key"]) or _active_alert(
        snapshot["solar_system_id"]
    )
    already_pinged = FeedAmarrFleetPing.objects.filter(
        cluster_key=snapshot["cluster_key"]
    ).exists()

    # Historical / inactive rollup rewrites: never open a new Discord thread.
    if existing is None:
        if already_pinged or not event.is_active or not _is_fresh_fleet(event):
            return False

    try:
        alert, created = _upsert_amarr_fleet_alert(
            snapshot=snapshot,
            existing=existing,
            discord_client=client,
        )
    except RateLimitException as exc:
        # Expected after DiscordClient retries; do not logger.exception
        # (that created CELERY-JV Sentry noise).
        logger.warning(
            "Amarr fleet ping rate-limited for cluster %s: %s",
            snapshot["cluster_key"],
            exc,
        )
        return False
    except HTTPError as exc:
        # Transient Discord 5xx or stale message 4xx on PATCH (CELERY-JM / KD).
        if _is_discord_edit_soft_fail(exc):
            logger.warning(
                "Amarr fleet ping Discord HTTP %s for cluster %s: %s",
                getattr(exc.response, "status_code", "?"),
                snapshot["cluster_key"],
                exc,
            )
            return False
        logger.exception(
            "Failed to send/update Amarr fleet ping for cluster %s",
            snapshot["cluster_key"],
        )
        return False
    except Exception:
        logger.exception(
            "Failed to send/update Amarr fleet ping for cluster %s",
            snapshot["cluster_key"],
        )
        return False
    if alert is None:
        return False

    _record_amarr_fleet_ping(
        cluster_key=snapshot["cluster_key"],
        alert=alert,
        solar_system_id=snapshot["solar_system_id"],
        created=created,
    )
    return True
