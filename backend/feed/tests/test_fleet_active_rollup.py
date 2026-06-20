from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from feed.constants import FACTION_CALDARI
from feed.helpers.ingest import upsert_feed_killmail_from_r2z2
from feed.models import FeedCluster
from feed.rollups.fleet_active import (
    _collapse_fleet_clusters,
    run_fleet_active_rollup,
)
from feed.rollups.registry import build_context
from feed.tests.helpers import make_killmail_payload


class FleetActiveRollupTestCase(TestCase):
    def test_collapse_fleet_clusters_merges_adjacent_buckets(self):
        base = timezone.now()
        clusters = [
            FeedCluster(
                cluster_key=f"fleet_engagement:30002542:500002:2026-06-19T20:{minute:02d}",
                cluster_type=FeedCluster.ClusterType.FLEET_ENGAGEMENT,
                solar_system_id=30002542,
                dominant_faction_id=500002,
                started_at=base + timedelta(minutes=minute),
                last_kill_at=base + timedelta(minutes=minute + 15),
                kill_count=8,
                pilot_count=10,
            )
            for minute in (0, 20, 40)
        ]

        collapsed = _collapse_fleet_clusters(clusters)

        self.assertEqual(len(collapsed), 1)
        representative, engagement_start = collapsed[0][:2]
        self.assertEqual(
            representative.last_kill_at, clusters[-1].last_kill_at
        )
        self.assertEqual(engagement_start, clusters[0].started_at)

    def test_collapse_fleet_clusters_keeps_separate_engagements(self):
        base = timezone.now()
        first = FeedCluster(
            cluster_key="fleet_engagement:30002542:500002:2026-06-19T10:00",
            cluster_type=FeedCluster.ClusterType.FLEET_ENGAGEMENT,
            solar_system_id=30002542,
            dominant_faction_id=500002,
            started_at=base,
            last_kill_at=base + timedelta(minutes=15),
            kill_count=8,
            pilot_count=10,
        )
        second = FeedCluster(
            cluster_key="fleet_engagement:30002542:500002:2026-06-19T14:00",
            cluster_type=FeedCluster.ClusterType.FLEET_ENGAGEMENT,
            solar_system_id=30002542,
            dominant_faction_id=500002,
            started_at=base + timedelta(hours=4),
            last_kill_at=base + timedelta(hours=4, minutes=15),
            kill_count=6,
            pilot_count=9,
        )

        collapsed = _collapse_fleet_clusters([first, second])

        self.assertEqual(len(collapsed), 2)

    def test_rollup_ignores_stale_cluster_dominant_faction(self):
        base = timezone.now()
        killmail_ids = []
        for i in range(3):
            payload = make_killmail_payload(
                88000000 + i,
                killmail_time=base,
                attacker_count=0,
            )
            raw = payload["killmail"]
            raw["attackers"] = [
                {
                    "character_id": 90000000 + j,
                    "corporation_id": 98000000,
                    "alliance_id": 99000000,
                    "faction_id": 500002,
                    "ship_type_id": 22468,
                    "damage_done": 1000,
                    "final_blow": j == 0,
                }
                for j in range(2)
            ] + [
                {
                    "character_id": 91000000 + j,
                    "corporation_id": 98000000,
                    "alliance_id": 99000000,
                    "faction_id": FACTION_CALDARI,
                    "ship_type_id": 22468,
                    "damage_done": 1000,
                    "final_blow": False,
                }
                for j in range(8)
            ]
            upsert_feed_killmail_from_r2z2(payload)
            killmail_ids.append(88000000 + i)

        FeedCluster.objects.create(
            cluster_key="fleet_engagement:30002542:500002:2026-06-19T20:00",
            cluster_type=FeedCluster.ClusterType.FLEET_ENGAGEMENT,
            solar_system_id=30002542,
            dominant_faction_id=500002,
            started_at=base,
            last_kill_at=base,
            kill_count=3,
            pilot_count=10,
            killmail_ids=killmail_ids,
        )

        ctx = build_context(
            base - timedelta(hours=1), base + timedelta(hours=1)
        )
        results = run_fleet_active_rollup(ctx)

        self.assertEqual(len(results), 0)
