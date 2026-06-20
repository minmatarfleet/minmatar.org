from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from feed.helpers.clusters import detect_clusters
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
