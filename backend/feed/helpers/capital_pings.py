from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from discord.client import DiscordClient
from discord.models import DiscordChannel
from eveuniverse.models import EveSolarSystem

from feed.constants import (
    AMAMAKE_SOLAR_SYSTEM_ID,
    CAPITAL_PING_MAX_AGE_SECONDS,
    CAPITAL_PING_MAX_LIGHT_YEARS,
    CAPITAL_PING_SESSION_SECONDS,
)
from feed.helpers.capital_ships import (
    capital_ships_on_killmail,
    killmail_involves_capital,
)
from feed.helpers.eve_names import resolve_type_names
from feed.helpers.ingest import parse_r2z2_payload
from feed.helpers.killmail_classify import is_npc_kill
from feed.helpers.system_distance import light_years_between_systems
from feed.models import FeedCapitalAlert, FeedCapitalPing

logger = logging.getLogger(__name__)

CAPITAL_ALERT_TITLE = "Capital ship within jump range spotted"
CAPITAL_ALERT_COLOR = 0x18ED09


def _capital_ping_channel_ids() -> list[int]:
    return list(
        DiscordChannel.objects.filter(
            receive_capital_pings=True,
            guild__is_active=True,
        ).values_list("channel_id", flat=True)
    )


def _system_label(solar_system_id: int) -> str:
    system = EveSolarSystem.objects.filter(id=solar_system_id).first()
    if system is None:
        system, _ = EveSolarSystem.objects.get_or_create_esi(
            id=solar_system_id
        )
    return system.name or f"System {solar_system_id}"


def _killmail_time_hhmm(killmail_time: str | None) -> str:
    if not killmail_time:
        return "??:??"
    parsed = parse_datetime(killmail_time)
    if parsed is None:
        return "??:??"
    return parsed.strftime("%H:%M")


def _capital_entries(raw: dict[str, Any]) -> list[dict[str, Any]]:
    capital_rows = capital_ships_on_killmail(raw)
    if not capital_rows:
        return []
    ship_names = resolve_type_names(
        [type_id for type_id, _, _ in capital_rows]
    )
    entries: list[dict[str, Any]] = []
    for type_id, count, role in capital_rows:
        entries.append(
            {
                "type_id": int(type_id),
                "name": ship_names.get(int(type_id), f"Type {type_id}"),
                "role": role,
                "count": int(count),
            }
        )
    return entries


def _merge_capitals(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[tuple[int, str], dict[str, Any]] = {}
    for entry in existing + incoming:
        key = (int(entry["type_id"]), str(entry["role"]))
        prior = merged.get(key)
        if prior is None:
            merged[key] = dict(entry)
            continue
        prior["count"] = max(
            int(prior.get("count") or 1),
            int(entry.get("count") or 1),
        )
        prior["name"] = entry.get("name") or prior.get("name")
    return list(merged.values())


def _capital_labels(capitals: list[dict[str, Any]]) -> list[str]:
    labels: list[str] = []
    for entry in capitals:
        name = entry.get("name") or f"Type {entry.get('type_id')}"
        role = entry.get("role")
        count = int(entry.get("count") or 1)
        if role == "victim":
            labels.append(f"{name} (victim)")
        elif count > 1:
            labels.append(f"{name} (attacking ×{count})")
        else:
            labels.append(f"{name} (attacking)")
    return labels


def _kill_entry(raw: dict[str, Any]) -> dict[str, Any]:
    victim = raw.get("victim") or {}
    ship_type_id = victim.get("ship_type_id")
    ship_names = resolve_type_names([ship_type_id] if ship_type_id else [])
    ship_name = (
        ship_names.get(int(ship_type_id), f"Type {ship_type_id}")
        if ship_type_id
        else "Unknown ship"
    )
    return {
        "killmail_id": int(raw["killmail_id"]),
        "ship_name": ship_name,
        "time_hhmm": _killmail_time_hhmm(raw.get("killmail_time")),
    }


def build_capital_alert_payload(
    *,
    system_name: str,
    distance_ly: float,
    capitals: list[dict[str, Any]],
    kills: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build Discord payload for a capital presence alert.

    The Kills line is only included once there is more than one killmail
    associated with the alert (follow-up activity edits the original message).
    """
    description_lines = [
        f"**System:** {system_name}",
        f"**Distance from Amamake:** {distance_ly:.1f} LY",
    ]
    capital_labels = _capital_labels(capitals)
    if capital_labels:
        description_lines.append(
            f"**Capital ships:** {', '.join(capital_labels)}"
        )
    if len(kills) > 1:
        kill_parts = [
            f"{kill['ship_name']} ({kill['time_hhmm']})" for kill in kills
        ]
        description_lines.append(f"Kills: {', '.join(kill_parts)}")

    embed: dict[str, Any] = {
        "type": "rich",
        "title": CAPITAL_ALERT_TITLE,
        "description": "\n".join(description_lines),
        "color": CAPITAL_ALERT_COLOR,
    }
    thumbnail_type_id = next(
        (int(entry["type_id"]) for entry in capitals if entry.get("type_id")),
        None,
    )
    if thumbnail_type_id:
        embed["thumbnail"] = {
            "url": (
                f"https://images.evetech.net/types/{thumbnail_type_id}"
                f"/render?size=64"
            ),
        }
    return {"embeds": [embed]}


# Backwards-compatible alias used by the smoke-test command.
def build_capital_ping_payload(
    raw: dict[str, Any],
    *,
    zkb: dict[str, Any],
    distance_ly: float,
) -> dict[str, Any]:
    del zkb  # presence alerts do not use zkb totals
    system_name = _system_label(int(raw["solar_system_id"]))
    capitals = _capital_entries(raw)
    kills = [_kill_entry(raw)]
    return build_capital_alert_payload(
        system_name=system_name,
        distance_ly=distance_ly,
        capitals=capitals,
        kills=kills,
    )


def _active_alert(solar_system_id: int) -> FeedCapitalAlert | None:
    cutoff = timezone.now() - timedelta(seconds=CAPITAL_PING_SESSION_SECONDS)
    return (
        FeedCapitalAlert.objects.filter(
            solar_system_id=solar_system_id,
            last_activity_at__gte=cutoff,
        )
        .order_by("-last_activity_at")
        .first()
    )


def _post_alert_messages(
    payload: dict[str, Any],
    *,
    discord_client: DiscordClient,
) -> list[dict[str, int]]:
    messages: list[dict[str, int]] = []
    for channel_id in _capital_ping_channel_ids():
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
    alert: FeedCapitalAlert,
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


def send_capital_ping_discord(
    raw: dict[str, Any],
    *,
    zkb: dict[str, Any],
    distance_ly: float,
    discord_client: DiscordClient | None = None,
) -> list[int]:
    """Post a fresh capital presence alert. Returns Discord message ids."""
    channel_ids = _capital_ping_channel_ids()
    if not channel_ids:
        logger.info("Capital ping skipped: no Discord channels configured")
        return []

    payload = build_capital_ping_payload(raw, zkb=zkb, distance_ly=distance_ly)
    client = discord_client or DiscordClient()
    messages = _post_alert_messages(payload, discord_client=client)
    return [message["message_id"] for message in messages]


def _age_gate_blocks(raw: dict[str, Any]) -> bool:
    killmail_time_str = raw.get("killmail_time")
    killmail_time = (
        parse_datetime(killmail_time_str) if killmail_time_str else None
    )
    if killmail_time is None:
        return False
    age_seconds = (timezone.now() - killmail_time).total_seconds()
    return age_seconds > CAPITAL_PING_MAX_AGE_SECONDS


def _create_capital_alert(
    *,
    solar_system_id: int,
    system_name: str,
    distance_ly: float,
    capitals: list[dict[str, Any]],
    kill: dict[str, Any],
    discord_client: DiscordClient,
) -> FeedCapitalAlert | None:
    discord_payload = build_capital_alert_payload(
        system_name=system_name,
        distance_ly=distance_ly,
        capitals=capitals,
        kills=[kill],
    )
    discord_messages = _post_alert_messages(
        discord_payload, discord_client=discord_client
    )
    if not discord_messages:
        return None
    return FeedCapitalAlert.objects.create(
        solar_system_id=solar_system_id,
        system_name=system_name,
        distance_ly=distance_ly,
        capitals=capitals,
        kills=[kill],
        discord_messages=discord_messages,
        last_activity_at=timezone.now(),
    )


def _update_capital_alert(
    alert: FeedCapitalAlert,
    *,
    system_name: str,
    distance_ly: float,
    capitals: list[dict[str, Any]],
    kill: dict[str, Any],
    discord_client: DiscordClient,
) -> FeedCapitalAlert:
    alert.capitals = _merge_capitals(alert.capitals or [], capitals)
    alert.kills = list(alert.kills or []) + [kill]
    alert.distance_ly = distance_ly
    alert.system_name = system_name
    alert.last_activity_at = timezone.now()
    discord_payload = build_capital_alert_payload(
        system_name=alert.system_name,
        distance_ly=alert.distance_ly,
        capitals=alert.capitals,
        kills=alert.kills,
    )
    _edit_alert_messages(alert, discord_payload, discord_client=discord_client)
    alert.save(
        update_fields=[
            "capitals",
            "kills",
            "distance_ly",
            "system_name",
            "last_activity_at",
        ]
    )
    return alert


def _record_capital_ping(
    *,
    killmail_id: int,
    alert: FeedCapitalAlert,
    solar_system_id: int,
    distance_ly: float,
    created: bool,
) -> None:
    first_message_id = None
    if alert.discord_messages:
        first_message_id = alert.discord_messages[0].get("message_id")
    FeedCapitalPing.objects.create(
        killmail_id=killmail_id,
        alert=alert,
        solar_system_id=solar_system_id,
        distance_ly=distance_ly,
        discord_message_id=first_message_id,
    )
    action = "created" if created else "updated with"
    logger.info(
        "Capital alert %s killmail %s in system %s (%.1f LY from Amamake)",
        action,
        killmail_id,
        solar_system_id,
        distance_ly,
    )


def maybe_notify_capital_kill(
    payload: dict[str, Any],
    *,
    discord_client: DiscordClient | None = None,
    apply_age_gate: bool = False,
) -> bool | None:
    """Evaluate an R2Z2 payload and create/update a capital presence alert.

    Returns True if a Discord message was created or edited, False if skipped
    (not eligible), and None if skipped solely due to the killmail age gate.
    """
    if not _capital_ping_channel_ids():
        return False

    raw, zkb, _ = parse_r2z2_payload(payload)
    if is_npc_kill(zkb):
        return False

    killmail_id = raw.get("killmail_id") or payload.get("killmail_id")
    solar_system_id = raw.get("solar_system_id")
    if not killmail_id or not solar_system_id:
        return False
    if FeedCapitalPing.objects.filter(killmail_id=killmail_id).exists():
        return False
    if not killmail_involves_capital(raw):
        return False

    distance_ly = light_years_between_systems(
        AMAMAKE_SOLAR_SYSTEM_ID,
        int(solar_system_id),
    )
    if distance_ly is None or distance_ly > CAPITAL_PING_MAX_LIGHT_YEARS:
        return False
    if apply_age_gate and _age_gate_blocks(raw):
        return None

    client = discord_client or DiscordClient()
    capitals = _capital_entries(raw)
    kill = _kill_entry(raw)
    system_name = _system_label(int(solar_system_id))
    existing = _active_alert(int(solar_system_id))
    created = existing is None

    try:
        if existing is None:
            alert = _create_capital_alert(
                solar_system_id=int(solar_system_id),
                system_name=system_name,
                distance_ly=distance_ly,
                capitals=capitals,
                kill=kill,
                discord_client=client,
            )
            if alert is None:
                return False
        else:
            alert = _update_capital_alert(
                existing,
                system_name=system_name,
                distance_ly=distance_ly,
                capitals=capitals,
                kill=kill,
                discord_client=client,
            )
    except Exception:
        logger.exception(
            "Failed to send/update capital ping for killmail %s", killmail_id
        )
        return False

    _record_capital_ping(
        killmail_id=int(killmail_id),
        alert=alert,
        solar_system_id=int(solar_system_id),
        distance_ly=distance_ly,
        created=created,
    )
    return True
