from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from feed.models import FeedCluster
from feed.rollups.fleet_active import _collapse_fleet_clusters


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
        representative, engagement_start = collapsed[0]
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
