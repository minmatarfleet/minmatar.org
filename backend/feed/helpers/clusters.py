from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta
from typing import Any

from django.db.models import F
from django.utils import timezone

from feed.constants import MILITIA_FACTION_IDS
from feed.helpers.killmail_classify import (
    dominant_attacker_faction,
    resolve_attacker_militia_factions,
)
from feed.models import FeedCluster, FeedKillmail
from feed.rollups.config import get_rollup_config


def _window_start(dt, minutes: int):
    return dt.replace(second=0, microsecond=0) - timedelta(
        minutes=dt.minute % minutes
    )


def _cluster_key(
    cluster_type: str,
    solar_system_id: int,
    faction_id: int | None,
    started_at,
    *,
    include_faction: bool = True,
) -> str:
    faction = faction_id if faction_id is not None else 0
    if hasattr(started_at, "replace"):
        started_at = started_at.replace(second=0, microsecond=0)
    if include_faction:
        return (
            f"{cluster_type}:{solar_system_id}:{faction}:"
            f"{started_at.strftime('%Y-%m-%dT%H:%M')}"
        )
    return (
        f"{cluster_type}:{solar_system_id}:"
        f"{started_at.strftime('%Y-%m-%dT%H:%M')}"
    )


def _kill_burst_bucket_suffix(started_bucket) -> str:
    if hasattr(started_bucket, "replace"):
        started_bucket = started_bucket.replace(second=0, microsecond=0)
    return started_bucket.strftime("%Y-%m-%dT%H:%M")


def _upsert_kill_burst_cluster(
    solar_system_id: int,
    started_bucket,
    stats: dict[str, Any],
) -> None:
    """One kill_burst cluster per system/time bucket regardless of faction."""
    bucket_suffix = _kill_burst_bucket_suffix(started_bucket)
    prefix = f"{FeedCluster.ClusterType.KILL_BURST}:{solar_system_id}:"
    siblings = [
        cluster
        for cluster in FeedCluster.objects.filter(
            cluster_type=FeedCluster.ClusterType.KILL_BURST,
            solar_system_id=solar_system_id,
        )
        if cluster.cluster_key.startswith(prefix)
        and cluster.cluster_key.endswith(f":{bucket_suffix}")
    ]

    merged_ids = set(stats["killmail_ids"])
    for sibling in siblings:
        merged_ids |= set(sibling.killmail_ids or [])

    if len(merged_ids) > len(stats["killmail_ids"]):
        killmails = list(
            FeedKillmail.objects.filter(killmail_id__in=merged_ids)
        )
        stats = build_cluster_stats(killmails)

    canonical_key = _cluster_key(
        FeedCluster.ClusterType.KILL_BURST,
        solar_system_id,
        None,
        started_bucket,
        include_faction=False,
    )
    FeedCluster.objects.update_or_create(
        cluster_key=canonical_key,
        defaults=_cluster_defaults(
            FeedCluster.ClusterType.KILL_BURST,
            solar_system_id,
            stats,
        ),
    )

    stale_keys = [
        cluster.pk
        for cluster in siblings
        if cluster.cluster_key != canonical_key
    ]
    if stale_keys:
        FeedCluster.objects.filter(pk__in=stale_keys).delete()


def _find_active_fleet_cluster(
    solar_system_id: int,
    faction_id: int | None,
    window_start,
    *,
    stale_minutes: int,
) -> FeedCluster | None:
    cutoff = window_start - timedelta(minutes=stale_minutes)
    active = FeedCluster.objects.filter(
        cluster_type=FeedCluster.ClusterType.FLEET_ENGAGEMENT,
        solar_system_id=solar_system_id,
        is_active=True,
        last_kill_at__gte=cutoff,
    ).order_by("-last_kill_at")

    exact = active.filter(dominant_faction_id=faction_id).first()
    if exact is not None:
        return exact

    # An orphan window whose dominant faction is unknown (NULL/0) still belongs
    # to the active fight in the system; likewise attach a newly-resolved faction
    # to a cluster whose faction could not previously be determined. This avoids
    # splitting one engagement across ``:0:`` and ``:<faction>:`` cluster keys.
    if faction_id is None:
        return active.first()
    return active.filter(dominant_faction_id__isnull=True).first()


def _merge_fleet_cluster(
    existing: FeedCluster,
    killmail_ids: list[int],
    *,
    faction_id: int | None = None,
) -> FeedCluster:
    merged_ids = sorted(set(existing.killmail_ids or []) | set(killmail_ids))
    killmails = list(FeedKillmail.objects.filter(killmail_id__in=merged_ids))
    scope = (
        faction_id if faction_id is not None else existing.dominant_faction_id
    )
    stats = build_cluster_stats(killmails, faction_id=scope)
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


def _attacker_faction_id(
    attacker: dict[str, Any],
    char_factions: dict[int, int],
) -> int | None:
    char_id = attacker.get("character_id")
    if not char_id:
        return None
    resolved = char_factions.get(char_id)
    if resolved in MILITIA_FACTION_IDS:
        return resolved
    tagged = attacker.get("faction_id")
    if tagged in MILITIA_FACTION_IDS:
        return tagged
    return None


def build_cluster_stats(
    killmails: list[FeedKillmail],
    *,
    faction_id: int | None = None,
) -> dict[str, Any]:
    """Aggregate killmails into cluster stats.

    When ``faction_id`` is set, only that militia's attackers and the killmails
    they appear on are counted. This keeps opposing fleets on the same grid as
    separate engagements instead of one mixed blob.
    """
    if not killmails:
        return {
            "dominant_faction_id": faction_id,
            "started_at": None,
            "last_kill_at": None,
            "kill_count": 0,
            "pilot_count": 0,
            "ship_counts": {},
            "attacker_ids": [],
            "killmail_ids": [],
        }

    raw_kms = [km.raw_killmail for km in killmails]
    char_factions = (
        resolve_attacker_militia_factions(raw_kms)
        if faction_id is not None
        else {}
    )

    attacker_ids: set[int] = set()
    ship_counts: Counter[str] = Counter()
    killmail_ids: list[int] = []
    scoped_kms: list[FeedKillmail] = []

    for km in killmails:
        faction_on_mail = False
        for attacker in km.attacker_summary or []:
            char_id = attacker.get("character_id")
            if not char_id:
                continue
            if faction_id is None:
                attacker_ids.add(char_id)
                continue
            if _attacker_faction_id(attacker, char_factions) == faction_id:
                attacker_ids.add(char_id)
                faction_on_mail = True
        if faction_id is None or faction_on_mail:
            scoped_kms.append(km)
            killmail_ids.append(km.killmail_id)
            ship_type = km.victim_ship_type_id
            if ship_type:
                ship_counts[str(ship_type)] += 1

    if faction_id is None:
        fleet_cfg = get_rollup_config("fleet_active")
        dominant = dominant_attacker_faction(
            raw_kms,
            threshold=fleet_cfg.get("dominant_faction_threshold", 0.75),
        )
    else:
        dominant = faction_id

    if not scoped_kms:
        return {
            "dominant_faction_id": dominant,
            "started_at": min(km.killmail_time for km in killmails),
            "last_kill_at": max(km.killmail_time for km in killmails),
            "kill_count": 0,
            "pilot_count": 0,
            "ship_counts": {},
            "attacker_ids": [],
            "killmail_ids": [],
        }

    return {
        "dominant_faction_id": dominant,
        "started_at": min(km.killmail_time for km in scoped_kms),
        "last_kill_at": max(km.killmail_time for km in scoped_kms),
        "kill_count": len(scoped_kms),
        "pilot_count": len(attacker_ids),
        "ship_counts": dict(ship_counts),
        "attacker_ids": sorted(attacker_ids),
        "killmail_ids": killmail_ids,
    }


def _militia_factions_in_window(
    killmails: list[FeedKillmail],
) -> dict[int, set[int]]:
    """Map militia faction_id -> attacker character ids in the window."""
    raw_kms = [km.raw_killmail for km in killmails]
    char_factions = resolve_attacker_militia_factions(raw_kms)
    faction_pilots: dict[int, set[int]] = defaultdict(set)
    for char_id, resolved in char_factions.items():
        if resolved in MILITIA_FACTION_IDS:
            faction_pilots[resolved].add(char_id)
    return faction_pilots


def _upsert_one_fleet_cluster(
    solar_system_id: int,
    stats: dict[str, Any],
    window_start,
    *,
    stale_minutes: int,
    max_duration: timedelta,
) -> int:
    """Merge into an active same-faction cluster or create a new one."""
    if stats["kill_count"] <= 0 or stats["started_at"] is None:
        return 0

    existing = _find_active_fleet_cluster(
        solar_system_id,
        stats["dominant_faction_id"],
        window_start,
        stale_minutes=stale_minutes,
    )
    if existing is not None:
        if stats["last_kill_at"] - existing.started_at > max_duration:
            FeedCluster.objects.filter(pk=existing.pk).update(
                is_active=False,
                ended_at=F("last_kill_at"),
                updated_at=timezone.now(),
            )
        else:
            _merge_fleet_cluster(
                existing,
                stats["killmail_ids"],
                faction_id=stats["dominant_faction_id"],
            )
            return 1

    key = _cluster_key(
        FeedCluster.ClusterType.FLEET_ENGAGEMENT,
        solar_system_id,
        stats["dominant_faction_id"],
        stats["started_at"],
    )
    FeedCluster.objects.update_or_create(
        cluster_key=key,
        defaults=_cluster_defaults(
            FeedCluster.ClusterType.FLEET_ENGAGEMENT,
            solar_system_id,
            stats,
        ),
    )
    return 1


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
            if cluster_type == FeedCluster.ClusterType.FLEET_ENGAGEMENT:
                fleet_cfg = get_rollup_config("fleet_active")
                stale_minutes = fleet_cfg.get("stale_minutes", 20)
                max_duration = timedelta(
                    minutes=fleet_cfg.get("max_duration_minutes", 90)
                )
                created = _upsert_fleet_engagement_window(
                    solar_system_id,
                    window_kills,
                    window_start,
                    min_kills=min_kills,
                    min_pilots=min_pilots,
                    stale_minutes=stale_minutes,
                    max_duration=max_duration,
                )
                if created:
                    upserted += created
                    i = j
                    continue
            else:
                stats = build_cluster_stats(window_kills)
                if stats["pilot_count"] >= min_pilots:
                    started_bucket = _window_start(
                        window_start, window_minutes
                    )
                    _upsert_kill_burst_cluster(
                        solar_system_id,
                        started_bucket,
                        stats,
                    )
                    upserted += 1
                    i = j
                    continue
        i += 1
    return upserted


def _upsert_fleet_engagement_window(
    solar_system_id: int,
    window_kills: list[FeedKillmail],
    window_start,
    *,
    min_kills: int,
    min_pilots: int,
    stale_minutes: int,
    max_duration: timedelta,
) -> int:
    """Emit one fleet cluster per militia faction with enough attackers.

    Opposing fleets on the same grid (e.g. Amarr Cerbs vs Minmatar) become
    separate engagements instead of a single mixed pilot blob.
    """
    faction_pilots = _militia_factions_in_window(window_kills)
    factions = [
        faction_id
        for faction_id, pilots in faction_pilots.items()
        if len(pilots) >= min_pilots
    ]

    if not factions:
        stats = build_cluster_stats(window_kills)
        if (
            stats["pilot_count"] >= min_pilots
            and stats["kill_count"] >= min_kills
        ):
            return _upsert_one_fleet_cluster(
                solar_system_id,
                stats,
                window_start,
                stale_minutes=stale_minutes,
                max_duration=max_duration,
            )
        return 0

    created = 0
    for faction_id in sorted(factions):
        stats = build_cluster_stats(window_kills, faction_id=faction_id)
        if (
            stats["pilot_count"] < min_pilots
            or stats["kill_count"] < min_kills
        ):
            continue
        created += _upsert_one_fleet_cluster(
            solar_system_id,
            stats,
            window_start,
            stale_minutes=stale_minutes,
            max_duration=max_duration,
        )
    return created


def _mark_stale_fleet_clusters(stale_minutes: int) -> None:
    cutoff = timezone.now() - timedelta(minutes=stale_minutes)
    FeedCluster.objects.filter(
        cluster_type=FeedCluster.ClusterType.FLEET_ENGAGEMENT,
        is_active=True,
        last_kill_at__lt=cutoff,
    ).update(
        is_active=False,
        ended_at=F("last_kill_at"),
        updated_at=timezone.now(),
    )
