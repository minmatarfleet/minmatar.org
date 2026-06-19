from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils.dateparse import parse_datetime

from feed.helpers.killmail_classify import (
    extract_militia_character_ids,
    is_npc_kill,
)
from feed.helpers.monitored_systems import is_monitored_system
from feed.models import FeedKillmail, FeedMilitiaFirstSeen


def parse_r2z2_payload(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], int | None]:
    """Extract (raw_killmail, zkb_meta, sequence_id) from R2Z2 JSON."""
    raw = payload.get("killmail") or payload
    zkb = payload.get("zkb") or raw.get("zkb") or {}
    sequence_id = payload.get("sequence_id") or payload.get("sequence")
    return raw, zkb, sequence_id


def upsert_feed_killmail_from_r2z2(
    payload: dict[str, Any],
    *,
    allowlist: frozenset[int] | None = None,
) -> FeedKillmail | None:
    """Ingest R2Z2 payload; returns None if discarded."""
    raw, zkb, sequence_id = parse_r2z2_payload(payload)
    if is_npc_kill(zkb):
        return None

    solar_system_id = raw.get("solar_system_id")
    if solar_system_id is None or not is_monitored_system(
        solar_system_id, allowlist
    ):
        return None

    killmail_id = raw.get("killmail_id") or payload.get("killmail_id")
    killmail_hash = payload.get("hash") or zkb.get("hash")
    if not killmail_id or not killmail_hash:
        return None

    killmail_time_str = raw.get("killmail_time")
    killmail_time = (
        parse_datetime(killmail_time_str) if killmail_time_str else None
    )
    if killmail_time is None:
        return None

    victim = raw.get("victim") or {}
    attackers = raw.get("attackers") or []
    attacker_summary = [
        {
            "character_id": a.get("character_id"),
            "corporation_id": a.get("corporation_id"),
            "alliance_id": a.get("alliance_id"),
            "faction_id": a.get("faction_id"),
            "ship_type_id": a.get("ship_type_id"),
            "damage_done": a.get("damage_done"),
            "final_blow": a.get("final_blow"),
        }
        for a in attackers
    ]

    with transaction.atomic():
        killmail, _ = FeedKillmail.objects.update_or_create(
            killmail_id=killmail_id,
            defaults={
                "hash": killmail_hash,
                "killmail_time": killmail_time,
                "solar_system_id": solar_system_id,
                "victim_character_id": victim.get("character_id"),
                "victim_ship_type_id": victim.get("ship_type_id"),
                "attacker_summary": attacker_summary,
                "raw_killmail": raw,
                "zkb_meta": zkb,
                "zkill_sequence_id": sequence_id,
            },
        )
        _record_militia_first_seen(killmail, raw)
    return killmail


def _record_militia_first_seen(
    killmail: FeedKillmail, raw: dict[str, Any]
) -> None:
    for character_id, faction_id, role in extract_militia_character_ids(raw):
        FeedMilitiaFirstSeen.objects.get_or_create(
            character_id=character_id,
            faction_id=faction_id,
            defaults={
                "first_seen_at": killmail.killmail_time,
                "first_seen_killmail_id": killmail.killmail_id,
                "role": role,
                "solar_system_id": killmail.solar_system_id,
            },
        )


def upsert_feed_killmail_from_raw(
    raw: dict[str, Any],
    *,
    zkb_meta: dict[str, Any] | None = None,
    allowlist: frozenset[int] | None = None,
) -> FeedKillmail | None:
    payload = {"killmail": raw, "zkb": zkb_meta or raw.get("zkb") or {}}
    return upsert_feed_killmail_from_r2z2(payload, allowlist=allowlist)
