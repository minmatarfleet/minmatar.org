from __future__ import annotations

from datetime import timedelta

from feed.constants import FACTION_AMARR, FACTION_MINMATAR
from feed.helpers.clusters import build_cluster_stats
from feed.helpers.killmail_classify import (
    dominant_attacker_faction,
    faction_to_accent_key,
)
from feed.helpers.eve_names import sample_fleet_roster
from feed.models import FeedCluster, FeedEvent, FeedKillmail
from feed.rollups.config import get_rollup_config, get_rollup_version
from feed.rollups.engagement_copy import build_militia_engagement_copy
from feed.rollups.types import RollupContext, RollupResult


def _system_name(ctx: RollupContext, solar_system_id: int) -> str:
    return ctx.system_names.get(solar_system_id, f"System {solar_system_id}")


def _faction_label(faction_id: int | None) -> str:
    if faction_id == FACTION_MINMATAR:
        return "Minmatar"
    if faction_id == FACTION_AMARR:
        return "Amarr"
    return "Pirate"


def _accent_for_faction(faction_id: int | None) -> str:
    key = faction_to_accent_key(faction_id)
    if key == "minmatar":
        return FeedEvent.Accent.MILITIA
    if key == "amarr":
        return FeedEvent.Accent.AMARR
    return FeedEvent.Accent.COMBAT


def _dominant_faction_for_cluster(cluster: FeedCluster) -> int | None:
    """Return the militia faction for a fleet cluster.

    When the cluster was stored as Amarr/Minmatar (faction-scoped detection),
    re-validate against that faction's attackers on the linked killmails so a
    mixed grid cannot flip labels — while still dropping stale wrong labels
    (e.g. Minmatar stamped on Caldari-heavy mails).
    """
    killmail_ids = cluster.killmail_ids or []
    if not killmail_ids:
        return None

    killmails = list(FeedKillmail.objects.filter(killmail_id__in=killmail_ids))
    raw = [km.raw_killmail for km in killmails]
    fleet_cfg = get_rollup_config("fleet_active")
    stored = cluster.dominant_faction_id

    if stored in (FACTION_AMARR, FACTION_MINMATAR):
        stats = build_cluster_stats(killmails, faction_id=stored)
        if stats["pilot_count"] > 5:
            return stored
        return None

    return dominant_attacker_faction(
        raw,
        threshold=fleet_cfg.get("dominant_faction_threshold", 0.75),
    )


def _collapse_fleet_clusters(
    clusters,
) -> list[list[tuple[FeedCluster, int | None]]]:
    """Group adjacent time-bucket splits of the same fight into chains.

    Each returned chain is an ordered (by ``started_at``) list of
    ``(cluster, faction_id)`` tuples that together represent one continuous
    engagement in a system for a single militia faction.
    """
    fleet_cfg = get_rollup_config("fleet_active")
    stale_minutes = fleet_cfg.get("stale_minutes", 20)
    stale_delta = timedelta(minutes=stale_minutes)
    max_duration = timedelta(minutes=fleet_cfg.get("max_duration_minutes", 90))
    chains: list[list[tuple[FeedCluster, int | None]]] = []
    for cluster in sorted(
        clusters,
        key=lambda row: (
            row.solar_system_id,
            row.started_at,
        ),
    ):
        faction = _dominant_faction_for_cluster(cluster)
        placed = False
        for chain in chains:
            last_cluster, last_faction = chain[-1]
            chain_start = chain[0][0].started_at
            if (
                last_cluster.solar_system_id == cluster.solar_system_id
                and last_faction == faction
                and cluster.started_at
                <= last_cluster.last_kill_at + stale_delta
                and cluster.last_kill_at - chain_start <= max_duration
            ):
                chain.append((cluster, faction))
                placed = True
                break
        if not placed:
            chains.append([(cluster, faction)])
    return chains


def _persist_fleet_chain(
    chain: list[tuple[FeedCluster, int | None]],
) -> tuple[FeedCluster, int | None]:
    """Collapse a chain into its earliest cluster and drop the extras.

    The earliest cluster becomes the canonical, stable identity for the fight.
    Killmails from later splits are merged into it and the sibling rows are
    deleted so a subsequent rollup pass cannot re-key the same engagement.
    """
    ordered = sorted(chain, key=lambda row: row[0].started_at)
    canonical = ordered[0][0]
    extras = [cluster for cluster, _ in ordered[1:]]
    if extras:
        merged_ids: set[int] = set(canonical.killmail_ids or [])
        for cluster in extras:
            merged_ids |= set(cluster.killmail_ids or [])
        killmails = list(
            FeedKillmail.objects.filter(killmail_id__in=merged_ids)
        )
        stats = build_cluster_stats(
            killmails, faction_id=canonical.dominant_faction_id
        )
        tip = max(
            (cluster for cluster, _ in ordered),
            key=lambda cluster: cluster.last_kill_at,
        )
        canonical.dominant_faction_id = stats["dominant_faction_id"]
        canonical.started_at = stats["started_at"]
        canonical.last_kill_at = stats["last_kill_at"]
        canonical.kill_count = stats["kill_count"]
        canonical.pilot_count = stats["pilot_count"]
        canonical.ship_counts = stats["ship_counts"]
        canonical.attacker_ids = stats["attacker_ids"]
        canonical.killmail_ids = stats["killmail_ids"]
        canonical.is_active = tip.is_active
        canonical.ended_at = None if tip.is_active else stats["last_kill_at"]
        canonical.save()
        FeedCluster.objects.filter(
            pk__in=[cluster.pk for cluster in extras]
        ).delete()

    faction = _dominant_faction_for_cluster(canonical)
    return canonical, faction


def _fleet_event_cluster_key(
    cluster: FeedCluster,
    *,
    faction_id: int | None,
) -> str:
    started = cluster.started_at.replace(second=0, microsecond=0)
    faction = faction_id if faction_id is not None else 0
    return (
        f"fleet_active:{cluster.solar_system_id}:{faction}:"
        f"{started.strftime('%Y-%m-%dT%H:%M')}"
    )


def run_fleet_active_rollup(ctx: RollupContext) -> list[RollupResult]:
    version = get_rollup_version("fleet_active")
    clusters = FeedCluster.objects.filter(
        cluster_type=FeedCluster.ClusterType.FLEET_ENGAGEMENT,
        last_kill_at__gte=ctx.since,
        last_kill_at__lte=ctx.until,
    )
    results: list[RollupResult] = []
    for chain in _collapse_fleet_clusters(clusters):
        cluster, faction_id = _persist_fleet_chain(chain)
        if faction_id is None or cluster.pilot_count <= 5:
            continue
        system = _system_name(ctx, cluster.solar_system_id)
        copy = build_militia_engagement_copy(
            faction_label=_faction_label(faction_id),
            system=system,
            kills=cluster.kill_count,
            pilots=cluster.pilot_count,
            started_at=cluster.started_at,
            last_kill_at=cluster.last_kill_at,
            ship_counts=cluster.ship_counts or {},
            is_active=cluster.is_active,
        )
        roster, roster_total = sample_fleet_roster(
            cluster.attacker_ids,
            faction_id=faction_id,
            limit=8,
        )
        faction_key = faction_to_accent_key(faction_id)
        key = _fleet_event_cluster_key(cluster, faction_id=faction_id)
        results.append(
            RollupResult(
                kind=FeedEvent.Kind.FLEET_ACTIVE,
                occurred_at=cluster.last_kill_at,
                title=copy.title,
                subheader=copy.subheader,
                preview=copy.preview,
                body=copy.preview,
                accent=_accent_for_faction(faction_id),
                payload={
                    "faction": faction_key,
                    "system_id": cluster.solar_system_id,
                    "system_name": system,
                    "related_cluster_key": cluster.cluster_key,
                    "roster": roster,
                    "roster_total": roster_total,
                    **copy.payload_extra,
                },
                rollup_code="fleet_active",
                rollup_version=version,
                cluster_key=key,
                is_active=cluster.is_active,
                killmail_ids=cluster.killmail_ids or [],
            )
        )
    return results
