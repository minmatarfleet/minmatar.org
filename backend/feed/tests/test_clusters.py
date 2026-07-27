from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from feed.helpers.clusters import _mark_stale_fleet_clusters, detect_clusters
from feed.helpers.ingest import upsert_feed_killmail_from_r2z2
from feed.management.commands.seed_feed_monitored_systems import (
    seed_from_fixture,
)
from feed.models import FeedCluster, FeedKillmail
from feed.rollups.registry import build_context, run_rollup
from feed.tests.helpers import make_killmail_payload


class ClusterRollupTestCase(TestCase):
    def setUp(self):
        seed_from_fixture()
        base = timezone.now()
        for i in range(10):
            payload = make_killmail_payload(
                200000 + i,
                killmail_time=base
                - timedelta(minutes=5)
                + timedelta(seconds=i * 30),
            )
            upsert_feed_killmail_from_r2z2(payload)

    def test_detect_kill_burst_cluster(self):
        count = detect_clusters(since_hours=1)
        self.assertGreater(count, 0)
        self.assertTrue(
            FeedCluster.objects.filter(
                cluster_type=FeedCluster.ClusterType.KILL_BURST
            ).exists()
        )

    def test_kill_burst_rollup(self):
        detect_clusters(since_hours=1)
        now = timezone.now()
        ctx = build_context(now - timedelta(hours=1), now)
        results = run_rollup("kill_burst", ctx)
        self.assertTrue(results)
        self.assertEqual(results[0].kind, "killmail_batch")
        cluster_keys = {result.cluster_key for result in results}
        self.assertEqual(len(cluster_keys), len(results))

    def test_kill_burst_merges_faction_key_variants(self):
        FeedCluster.objects.all().delete()
        base = timezone.now() - timedelta(minutes=5)
        bucket = base.replace(second=0, microsecond=0) - timedelta(
            minutes=base.minute % 15
        )
        bucket_str = bucket.strftime("%Y-%m-%dT%H:%M")
        killmail_ids = []
        for i in range(10):
            payload = make_killmail_payload(
                400000 + i,
                killmail_time=base + timedelta(seconds=i * 30),
            )
            upsert_feed_killmail_from_r2z2(payload)
            killmail_ids.append(400000 + i)

        FeedCluster.objects.create(
            cluster_key=f"kill_burst:30002538:500002:{bucket_str}",
            cluster_type=FeedCluster.ClusterType.KILL_BURST,
            solar_system_id=30002538,
            dominant_faction_id=500002,
            started_at=base,
            last_kill_at=base + timedelta(minutes=5),
            kill_count=10,
            pilot_count=10,
            killmail_ids=killmail_ids,
        )

        detect_clusters(since_hours=1)

        burst_clusters = FeedCluster.objects.filter(
            cluster_type=FeedCluster.ClusterType.KILL_BURST,
            solar_system_id=30002538,
        )
        matching = [
            cluster
            for cluster in burst_clusters
            if cluster.cluster_key.endswith(f":{bucket_str}")
            or cluster.cluster_key == f"kill_burst:30002538:{bucket_str}"
        ]
        self.assertEqual(len(matching), 1)
        self.assertEqual(
            matching[0].cluster_key,
            f"kill_burst:30002538:{bucket_str}",
        )

    def test_sustained_fleet_fight_produces_one_cluster(self):
        FeedKillmail.objects.all().delete()
        FeedCluster.objects.all().delete()
        base = timezone.now() - timedelta(hours=1)
        kill_minutes = [0, 1, 2, 3, 4, 5, 6, 7, 25, 30, 35, 40]
        for i, minute in enumerate(kill_minutes):
            payload = make_killmail_payload(
                300000 + i,
                killmail_time=base + timedelta(minutes=minute),
                attacker_count=8,
            )
            upsert_feed_killmail_from_r2z2(payload)

        detect_clusters(since_hours=2)
        fleet_clusters = FeedCluster.objects.filter(
            cluster_type=FeedCluster.ClusterType.FLEET_ENGAGEMENT,
            solar_system_id=30002538,
            dominant_faction_id=500002,
        )
        self.assertEqual(fleet_clusters.count(), 1)
        cluster = fleet_clusters.get()
        self.assertGreaterEqual(cluster.kill_count, 5)
        self.assertGreaterEqual(cluster.pilot_count, 8)

    def test_continuous_fight_under_max_duration_stays_one_cluster(self):
        """Kills spanning <90m with <20m gaps stay a single engagement."""
        FeedKillmail.objects.all().delete()
        FeedCluster.objects.all().delete()
        base = timezone.now() - timedelta(hours=2)
        killmail_id = 310000
        # Burst every 15m for 75 minutes — under the 90m cap, gaps < stale.
        for segment in range(6):
            segment_start = base + timedelta(minutes=segment * 15)
            for i in range(6):
                payload = make_killmail_payload(
                    killmail_id,
                    killmail_time=segment_start + timedelta(seconds=i * 20),
                    attacker_count=8,
                )
                upsert_feed_killmail_from_r2z2(payload)
                killmail_id += 1

        detect_clusters(since_hours=3)
        fleet_clusters = FeedCluster.objects.filter(
            cluster_type=FeedCluster.ClusterType.FLEET_ENGAGEMENT,
            solar_system_id=30002538,
        )
        self.assertEqual(fleet_clusters.count(), 1)
        cluster = fleet_clusters.get()
        span = cluster.last_kill_at - cluster.started_at
        self.assertLessEqual(span, timedelta(minutes=90))

    def test_continuous_fight_over_max_duration_splits_clusters(self):
        """Busy-system mega-chain: kills never gap 20m but exceed 90m."""
        FeedKillmail.objects.all().delete()
        FeedCluster.objects.all().delete()
        base = timezone.now() - timedelta(hours=3)
        killmail_id = 320000
        # Burst every 15m for 120 minutes (>90m cap, gaps always <20m).
        for segment in range(9):
            segment_start = base + timedelta(minutes=segment * 15)
            for i in range(6):
                payload = make_killmail_payload(
                    killmail_id,
                    killmail_time=segment_start + timedelta(seconds=i * 20),
                    attacker_count=8,
                )
                upsert_feed_killmail_from_r2z2(payload)
                killmail_id += 1

        detect_clusters(since_hours=4)
        fleet_clusters = list(
            FeedCluster.objects.filter(
                cluster_type=FeedCluster.ClusterType.FLEET_ENGAGEMENT,
                solar_system_id=30002538,
            ).order_by("started_at")
        )
        self.assertGreaterEqual(len(fleet_clusters), 2)
        for cluster in fleet_clusters:
            span = cluster.last_kill_at - cluster.started_at
            self.assertLessEqual(span, timedelta(minutes=90))
        # First segment closed when the cap forced a split.
        self.assertFalse(fleet_clusters[0].is_active)
        self.assertIsNotNone(fleet_clusters[0].ended_at)

    def test_mark_stale_fleet_clusters_deactivates_and_sets_ended_at(self):
        """Stale active fleet clusters are deactivated via a single queryset update."""
        FeedCluster.objects.all().delete()
        last_kill_at = timezone.now() - timedelta(minutes=30)
        stale_cluster = FeedCluster.objects.create(
            cluster_key="fleet_engagement:30002538:500002:stale",
            cluster_type=FeedCluster.ClusterType.FLEET_ENGAGEMENT,
            solar_system_id=30002538,
            dominant_faction_id=500002,
            started_at=last_kill_at - timedelta(minutes=10),
            last_kill_at=last_kill_at,
            is_active=True,
            kill_count=5,
            pilot_count=8,
        )
        fresh_cluster = FeedCluster.objects.create(
            cluster_key="fleet_engagement:30002538:500002:fresh",
            cluster_type=FeedCluster.ClusterType.FLEET_ENGAGEMENT,
            solar_system_id=30002538,
            dominant_faction_id=500002,
            started_at=timezone.now() - timedelta(minutes=2),
            last_kill_at=timezone.now(),
            is_active=True,
            kill_count=5,
            pilot_count=8,
        )

        _mark_stale_fleet_clusters(stale_minutes=20)

        stale_cluster.refresh_from_db()
        fresh_cluster.refresh_from_db()
        self.assertFalse(stale_cluster.is_active)
        self.assertEqual(stale_cluster.ended_at, stale_cluster.last_kill_at)
        self.assertTrue(fresh_cluster.is_active)
        self.assertIsNone(fresh_cluster.ended_at)
