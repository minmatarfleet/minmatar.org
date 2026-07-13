from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from django.utils.dateparse import parse_datetime

from discord.client import DiscordClient
from discord.models import DiscordChannel
from eveonline.client import EsiClient
from eveuniverse.models import EveSolarSystem

from feed.constants import (
    AMAMAKE_SOLAR_SYSTEM_ID,
    CAPITAL_PING_MAX_LIGHT_YEARS,
)
from feed.helpers.capital_ships import (
    capital_ships_on_killmail,
    killmail_involves_capital,
)
from feed.helpers.eve_names import resolve_character_names, resolve_type_names
from feed.helpers.ingest import parse_r2z2_payload
from feed.helpers.killmail_classify import is_npc_kill
from feed.helpers.system_distance import light_years_between_systems
from feed.models import FeedCapitalPing

logger = logging.getLogger(__name__)


def _capital_ping_channel_ids() -> list[int]:
    return list(
        DiscordChannel.objects.filter(
            receive_capital_pings=True,
            guild__is_active=True,
        ).values_list("channel_id", flat=True)
    )


def _resolve_entity_names(entity_ids: set[int]) -> dict[int, str]:
    if not entity_ids:
        return {}

    names: dict[int, str] = {}
    client = EsiClient(None)
    sorted_ids = sorted(entity_ids)
    for index in range(0, len(sorted_ids), 1000):
        chunk = sorted_ids[index : index + 1000]
        response = client.resolve_universe_names(chunk)
        if response.success():
            for row in response.results():
                names[row["id"]] = row["name"]
    for entity_id in entity_ids:
        names.setdefault(entity_id, f"ID {entity_id}")
    return names


def _system_label(solar_system_id: int) -> str:
    system = EveSolarSystem.objects.filter(id=solar_system_id).first()
    if system is None:
        system, _ = EveSolarSystem.objects.get_or_create_esi(
            id=solar_system_id
        )
    return system.name or f"System {solar_system_id}"


def _format_isk(value: float | int | None) -> str:
    if value is None:
        return "unknown ISK"
    amount = float(value)
    if amount >= 1_000_000_000:
        return f"{amount / 1_000_000_000:.2f}b ISK"
    if amount >= 1_000_000:
        return f"{amount / 1_000_000:.2f}m ISK"
    if amount >= 1_000:
        return f"{amount / 1_000:.2f}k ISK"
    return f"{amount:.0f} ISK"


def _attacker_stats(
    attackers: list[dict[str, Any]],
) -> tuple[int, dict[str, Any] | None, tuple[int, int] | None, int | None]:
    """Return pilot count, final blow, top alliance (id, count), top ship type id."""
    pilot_ids = {
        attacker.get("character_id")
        for attacker in attackers
        if attacker.get("character_id")
        and attacker.get("corporation_id") != 1000125
    }
    pilot_ids.discard(None)

    final_blow = next(
        (attacker for attacker in attackers if attacker.get("final_blow")),
        None,
    )

    alliance_counts: Counter[int] = Counter()
    ship_counts: Counter[int] = Counter()
    for attacker in attackers:
        if attacker.get("corporation_id") == 1000125:
            continue
        alliance_id = attacker.get("alliance_id")
        if alliance_id:
            alliance_counts[alliance_id] += 1
        ship_type_id = attacker.get("ship_type_id")
        if ship_type_id:
            ship_counts[ship_type_id] += 1

    top_alliance = (
        alliance_counts.most_common(1)[0] if alliance_counts else None
    )
    top_ship_type_id = (
        ship_counts.most_common(1)[0][0] if ship_counts else None
    )
    return len(pilot_ids), final_blow, top_alliance, top_ship_type_id


def _collect_name_ids(
    *,
    victim_char_id: int | None,
    victim_corp_id: int | None,
    final_blow: dict[str, Any] | None,
    top_alliance: tuple[int, int] | None,
) -> set[int]:
    name_ids: set[int] = set()
    if victim_char_id:
        name_ids.add(int(victim_char_id))
    if victim_corp_id:
        name_ids.add(int(victim_corp_id))
    if final_blow:
        for key in ("character_id", "corporation_id", "alliance_id"):
            value = final_blow.get(key)
            if value:
                name_ids.add(int(value))
    if top_alliance is not None:
        name_ids.add(int(top_alliance[0]))
    return name_ids


def _capital_type_ids_for_names(raw: dict[str, Any]) -> list[int]:
    return [row[0] for row in capital_ships_on_killmail(raw)]


def _victim_labels(
    *,
    victim_char_id: int | None,
    victim_corp_id: int | None,
    victim_ship_type_id: int | None,
    char_names: dict[int, str],
    entity_names: dict[int, str],
    ship_names: dict[int, str],
) -> tuple[str, str, str]:
    victim_name = char_names.get(
        int(victim_char_id),
        f"Pilot {victim_char_id}" if victim_char_id else "Unknown pilot",
    )
    victim_corp = entity_names.get(
        int(victim_corp_id),
        f"Corp {victim_corp_id}" if victim_corp_id else "Unknown corp",
    )
    victim_ship = ship_names.get(
        int(victim_ship_type_id),
        (
            f"Type {victim_ship_type_id}"
            if victim_ship_type_id
            else "Unknown ship"
        ),
    )
    return victim_name, victim_corp, victim_ship


def _append_final_blow_line(
    description_lines: list[str],
    *,
    final_blow: dict[str, Any],
    char_names: dict[int, str],
    entity_names: dict[int, str],
    ship_names: dict[int, str],
) -> None:
    fb_char = final_blow.get("character_id")
    fb_corp = final_blow.get("corporation_id")
    fb_ship = final_blow.get("ship_type_id")
    fb_char_name = char_names.get(
        int(fb_char), f"Pilot {fb_char}" if fb_char else "Unknown pilot"
    )
    fb_corp_name = entity_names.get(
        int(fb_corp), f"Corp {fb_corp}" if fb_corp else "Unknown corp"
    )
    fb_ship_name = ship_names.get(
        int(fb_ship), f"Type {fb_ship}" if fb_ship else "Unknown ship"
    )
    description_lines.append(
        f"Final blow by **{fb_char_name}** ({fb_corp_name}) in a **{fb_ship_name}**."
    )


def _append_attacker_summary_lines(
    description_lines: list[str],
    *,
    attackers: list[dict[str, Any]],
    pilot_count: int,
    top_alliance: tuple[int, int] | None,
    top_ship_type_id: int | None,
    entity_names: dict[int, str],
    ship_names: dict[int, str],
) -> None:
    description_lines.append(
        f"**Attackers:** {len(attackers)} ({pilot_count} pilots)"
    )
    if top_alliance is not None:
        alliance_id, alliance_count = top_alliance
        alliance_name = entity_names.get(
            alliance_id, f"Alliance {alliance_id}"
        )
        description_lines.append(
            f"**Main group:** {alliance_name} ({alliance_count})"
        )
    if top_ship_type_id is None:
        return

    top_ship_name = ship_names.get(
        top_ship_type_id, f"Type {top_ship_type_id}"
    )
    top_ship_count = Counter(
        attacker.get("ship_type_id")
        for attacker in attackers
        if attacker.get("ship_type_id")
        and attacker.get("corporation_id") != 1000125
    )[top_ship_type_id]
    description_lines.append(
        f"**Top attacking ship:** {top_ship_name} ({top_ship_count})"
    )


def _append_capital_ship_lines(
    description_lines: list[str],
    *,
    raw: dict[str, Any],
    ship_names: dict[int, str],
) -> None:
    capital_rows = capital_ships_on_killmail(raw)
    if not capital_rows:
        return

    capital_labels: list[str] = []
    for type_id, count, role in capital_rows:
        name = ship_names.get(int(type_id), f"Type {type_id}")
        if role == "victim":
            capital_labels.append(f"{name} (victim)")
        elif count > 1:
            capital_labels.append(f"{name} (attacking ×{count})")
        else:
            capital_labels.append(f"{name} (attacking)")
    description_lines.append(
        f"**Capital ships involved:** {', '.join(capital_labels)}"
    )


def _zkill_footer_text(killmail_time: str | None) -> str:
    if not killmail_time:
        return "zKillboard"
    parsed = parse_datetime(killmail_time)
    if parsed is None:
        return "zKillboard"
    return f"zKillboard | {parsed.strftime('%Y-%m-%d %H:%M')} UTC"


def _build_description_lines(
    raw: dict[str, Any],
    *,
    zkb: dict[str, Any],
    distance_ly: float,
) -> tuple[list[str], str, str, int | None]:
    victim = raw.get("victim") or {}
    attackers = raw.get("attackers") or []
    victim_char_id = victim.get("character_id")
    victim_corp_id = victim.get("corporation_id")
    victim_ship_type_id = victim.get("ship_type_id")

    pilot_count, final_blow, top_alliance, top_ship_type_id = _attacker_stats(
        attackers
    )
    name_ids = _collect_name_ids(
        victim_char_id=victim_char_id,
        victim_corp_id=victim_corp_id,
        final_blow=final_blow,
        top_alliance=top_alliance,
    )
    char_names = resolve_character_names(
        [
            victim_char_id,
            final_blow.get("character_id") if final_blow else None,
        ]
    )
    entity_names = _resolve_entity_names(name_ids)
    ship_names = resolve_type_names(
        [
            victim_ship_type_id,
            top_ship_type_id,
            final_blow.get("ship_type_id") if final_blow else None,
            *_capital_type_ids_for_names(raw),
        ]
    )
    system_name = _system_label(int(raw["solar_system_id"]))
    victim_name, victim_corp, victim_ship = _victim_labels(
        victim_char_id=victim_char_id,
        victim_corp_id=victim_corp_id,
        victim_ship_type_id=victim_ship_type_id,
        char_names=char_names,
        entity_names=entity_names,
        ship_names=ship_names,
    )

    description_lines = [
        (
            f"**{victim_name}** ({victim_corp}) lost their **{victim_ship}** "
            f"in **{system_name}** worth **{_format_isk(zkb.get('totalValue'))}**."
        )
    ]
    if final_blow:
        _append_final_blow_line(
            description_lines,
            final_blow=final_blow,
            char_names=char_names,
            entity_names=entity_names,
            ship_names=ship_names,
        )
    _append_attacker_summary_lines(
        description_lines,
        attackers=attackers,
        pilot_count=pilot_count,
        top_alliance=top_alliance,
        top_ship_type_id=top_ship_type_id,
        entity_names=entity_names,
        ship_names=ship_names,
    )
    _append_capital_ship_lines(
        description_lines,
        raw=raw,
        ship_names=ship_names,
    )
    description_lines.append(
        f"**Distance from Amamake:** {distance_ly:.1f} LY"
    )
    return description_lines, system_name, victim_ship, victim_ship_type_id


def build_capital_ping_payload(
    raw: dict[str, Any],
    *,
    zkb: dict[str, Any],
    distance_ly: float,
) -> dict[str, Any]:
    killmail_id = int(raw["killmail_id"])
    description_lines, system_name, victim_ship, victim_ship_type_id = (
        _build_description_lines(raw, zkb=zkb, distance_ly=distance_ly)
    )

    embed: dict[str, Any] = {
        "type": "rich",
        "title": f"{system_name} | {victim_ship} | Killmail",
        "url": f"https://zkillboard.com/kill/{killmail_id}/",
        "description": "\n".join(description_lines),
        "color": 0x18ED09,
        "footer": {"text": _zkill_footer_text(raw.get("killmail_time"))},
    }
    if victim_ship_type_id:
        embed["thumbnail"] = {
            "url": (
                f"https://images.evetech.net/types/{victim_ship_type_id}/render?size=64"
            ),
        }

    return {
        "embeds": [embed],
    }


def send_capital_ping_discord(
    raw: dict[str, Any],
    *,
    zkb: dict[str, Any],
    distance_ly: float,
    discord_client: DiscordClient | None = None,
) -> list[int]:
    channel_ids = _capital_ping_channel_ids()
    if not channel_ids:
        logger.info("Capital ping skipped: no Discord channels configured")
        return []

    payload = build_capital_ping_payload(raw, zkb=zkb, distance_ly=distance_ly)
    client = discord_client or DiscordClient()
    message_ids: list[int] = []
    for channel_id in channel_ids:
        response = client.create_message(
            channel_id=channel_id, payload=payload
        )
        message_id = response.json().get("id")
        if message_id:
            message_ids.append(int(message_id))
    return message_ids


def maybe_notify_capital_kill(
    payload: dict[str, Any],
    *,
    discord_client: DiscordClient | None = None,
) -> bool:
    """Evaluate an R2Z2 payload and post a Discord ping when criteria match."""
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

    try:
        message_ids = send_capital_ping_discord(
            raw,
            zkb=zkb,
            distance_ly=distance_ly,
            discord_client=discord_client,
        )
    except Exception:
        logger.exception(
            "Failed to send capital ping for killmail %s", killmail_id
        )
        return False

    if not message_ids:
        return False

    FeedCapitalPing.objects.create(
        killmail_id=killmail_id,
        solar_system_id=solar_system_id,
        distance_ly=distance_ly,
        discord_message_id=message_ids[0],
    )
    logger.info(
        "Capital ping sent for killmail %s in system %s (%.1f LY from Amamake)",
        killmail_id,
        solar_system_id,
        distance_ly,
    )
    return True
