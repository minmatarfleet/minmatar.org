from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta
from typing import Any

from django.utils import timezone

from feed.helpers.killmail_classify import dominant_attacker_faction
from feed.models import FeedCluster, FeedKillmail
from feed.rollups.config import get_rollup_config


def _window_start(dt, minutes: int):
    return dt.replace(second=0, microsecond=0) - timedelta(
        minutes=dt.minute % minutes
    )


def _cluster_key(
    cluster_type: str, solar_system_id: int, faction_id: int | None, started_at
) -> str:
    faction = faction_id if faction_id is not None else 0
    if hasattr(started_at, "replace"):
        started_at = started_at.replace(second=0, microsecond=0)
    return f"{cluster_type}:{solar_system_id}:{faction}:{started_at.strftime('%Y-%m-%dT%H:%M')}"


def _find_active_fleet_cluster(
    solar_system_id: int,
    faction_id: int | None,
    window_start,
    *,
    stale_minutes: int,
) -> FeedCluster | None:
    cutoff = window_start - timedelta(minutes=stale_minutes)
    return (
        FeedCluster.objects.filter(
            cluster_type=FeedCluster.ClusterType.FLEET_ENGAGEMENT,
            solar_system_id=solar_system_id,
            dominant_faction_id=faction_id,
            is_active=True,
            last_kill_at__gte=cutoff,
        )
        .order_by("-last_kill_at")
        .first()
    )


def _merge_fleet_cluster(
    existing: FeedCluster, killmail_ids: list[int]
) -> FeedCluster:
    merged_ids = sorted(set(existing.killmail_ids or []) | set(killmail_ids))
    killmails = list(FeedKillmail.objects.filter(killmail_id__in=merged_ids))
    stats = _build_cluster_stats(killmails)
    existing.dominant_faction_id = stats["dominant_faction_id"]
    existing.started_at = stats["started_at"]
    existing.last_kill_at = stats["last_kill_at"]
    existing.kill_count = stats["kill_count"]
    existing.pilot_count = stats["pilot_count"]
    existing.ship_counts = stats["ship_counts"]
    existing.attacker_ids = stats["attacker_ids"]
    existing.killmail_ids = stats["killmail_ids"]
    existing.is_active = True
    existing.ended_at = None
    existing.save()
    return existing


def _cluster_defaults(
    cluster_type: str,
    solar_system_id: int,
    stats: dict[str, Any],
) -> dict[str, Any]:
    return {
        "cluster_type": cluster_type,
        "solar_system_id": solar_system_id,
        "dominant_faction_id": stats["dominant_faction_id"],
        "started_at": stats["started_at"],
        "last_kill_at": stats["last_kill_at"],
        "kill_count": stats["kill_count"],
        "pilot_count": stats["pilot_count"],
        "ship_counts": stats["ship_counts"],
        "attacker_ids": stats["attacker_ids"],
        "killmail_ids": stats["killmail_ids"],
        "is_active": cluster_type == FeedCluster.ClusterType.FLEET_ENGAGEMENT,
    }


def _build_cluster_stats(killmails: list[FeedKillmail]) -> dict[str, Any]:
    attacker_ids: set[int] = set()
    ship_counts: Counter[str] = Counter()
    killmail_ids: list[int] = []
    raw_kms: list[dict] = []

    for km in killmails:
        killmail_ids.append(km.killmail_id)
        raw_kms.append(km.raw_killmail)
        ship_type = km.victim_ship_type_id
        if ship_type:
            ship_counts[str(ship_type)] += 1
        for attacker in km.attacker_summary or []:
            char_id = attacker.get("character_id")
            if char_id:
                attacker_ids.add(char_id)

    dominant = dominant_attacker_faction(raw_kms)
    started_at = min(km.killmail_time for km in killmails)
    last_kill_at = max(km.killmail_time for km in killmails)

    return {
        "dominant_faction_id": dominant,
        "started_at": started_at,
        "last_kill_at": last_kill_at,
        "kill_count": len(killmails),
        "pilot_count": len(attacker_ids),
        "ship_counts": dict(ship_counts),
        "attacker_ids": sorted(attacker_ids),
        "killmail_ids": killmail_ids,
    }


def detect_clusters(*, since_hours: int = 48) -> int:
    """Detect kill_burst and fleet_engagement clusters from FeedKillmail rows."""
    now = timezone.now()
    since = now - timedelta(hours=since_hours)
    kill_burst_cfg = get_rollup_config("kill_burst")
    fleet_cfg = get_rollup_config("fleet_active")

    kb_window = kill_burst_cfg.get("window_minutes", 15)
    kb_min_kills = kill_burst_cfg.get("min_kills", 8)
    fleet_window = fleet_cfg.get("window_minutes", 20)
    fleet_min_kills = fleet_cfg.get("min_kills", 5)
    fleet_min_pilots = fleet_cfg.get("min_pilots", 8)
    stale_minutes = fleet_cfg.get("stale_minutes", 20)

    killmails = list(
        FeedKillmail.objects.filter(killmail_time__gte=since).order_by(
            "killmail_time"
        )
    )
    by_system: dict[int, list[FeedKillmail]] = defaultdict(list)
    for km in killmails:
        by_system[km.solar_system_id].append(km)

    upserted = 0
    for solar_system_id, system_kills in by_system.items():
        upserted += _detect_for_system(
            solar_system_id,
            system_kills,
            kb_window,
            kb_min_kills,
            fleet_window,
            fleet_min_kills,
            fleet_min_pilots,
        )

    _mark_stale_fleet_clusters(stale_minutes)
    return upserted


def _detect_for_system(
    solar_system_id: int,
    kills: list[FeedKillmail],
    kb_window: int,
    kb_min_kills: int,
    fleet_window: int,
    fleet_min_kills: int,
    fleet_min_pilots: int,
) -> int:
    count = 0
    count += _sliding_window_clusters(
        kills,
        solar_system_id,
        FeedCluster.ClusterType.KILL_BURST,
        kb_window,
        kb_min_kills,
        min_pilots=0,
    )
    count += _sliding_window_clusters(
        kills,
        solar_system_id,
        FeedCluster.ClusterType.FLEET_ENGAGEMENT,
        fleet_window,
        fleet_min_kills,
        min_pilots=fleet_min_pilots,
    )
    return count


def _sliding_window_clusters(
    kills: list[FeedKillmail],
    solar_system_id: int,
    cluster_type: str,
    window_minutes: int,
    min_kills: int,
    *,
    min_pilots: int,
) -> int:
    if len(kills) < min_kills:
        return 0

    upserted = 0
    window_delta = timedelta(minutes=window_minutes)
    i = 0
    while i < len(kills):
        window_start = kills[i].killmail_time
        window_end = window_start + window_delta
        window_kills = [kills[i]]
        j = i + 1
        while j < len(kills) and kills[j].killmail_time <= window_end:
            window_kills.append(kills[j])
            j += 1

        if len(window_kills) >= min_kills:
            stats = _build_cluster_stats(window_kills)
            if stats["pilot_count"] >= min_pilots:
                if cluster_type == FeedCluster.ClusterType.FLEET_ENGAGEMENT:
                    stale_minutes = get_rollup_config("fleet_active").get(
                        "stale_minutes", 20
                    )
                    existing = _find_active_fleet_cluster(
                        solar_system_id,
                        stats["dominant_faction_id"],
                        window_start,
                        stale_minutes=stale_minutes,
                    )
                    if existing is not None:
                        _merge_fleet_cluster(existing, stats["killmail_ids"])
                        upserted += 1
                        i = j
                        continue
                    key = _cluster_key(
                        cluster_type,
                        solar_system_id,
                        stats["dominant_faction_id"],
                        stats["started_at"],
                    )
                else:
                    started_bucket = _window_start(
                        window_start, window_minutes
                    )
                    key = _cluster_key(
                        cluster_type,
                        solar_system_id,
                        stats["dominant_faction_id"],
                        started_bucket,
                    )
                FeedCluster.objects.update_or_create(
                    cluster_key=key,
                    defaults=_cluster_defaults(
                        cluster_type, solar_system_id, stats
                    ),
                )
                upserted += 1
                i = j
                continue
        i += 1
    return upserted


def _mark_stale_fleet_clusters(stale_minutes: int) -> None:
    cutoff = timezone.now() - timedelta(minutes=stale_minutes)
    stale = FeedCluster.objects.filter(
        cluster_type=FeedCluster.ClusterType.FLEET_ENGAGEMENT,
        is_active=True,
        last_kill_at__lt=cutoff,
    )
    for cluster in stale:
        cluster.is_active = False
        cluster.ended_at = cluster.last_kill_at
        cluster.save(update_fields=["is_active", "ended_at", "updated_at"])
