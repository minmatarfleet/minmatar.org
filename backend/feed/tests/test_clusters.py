from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from feed.helpers.clusters import detect_clusters
from feed.helpers.ingest import upsert_feed_killmail_from_r2z2
from feed.management.commands.seed_feed_monitored_systems import (
    seed_from_fixture,
)
from feed.models import FeedCluster, FeedMilitiaFirstSeen
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

    def test_militia_first_seen_on_ingest(self):
        self.assertTrue(
            FeedMilitiaFirstSeen.objects.filter(faction_id=500002).exists()
        )

    def test_kill_burst_rollup(self):
        detect_clusters(since_hours=1)
        now = timezone.now()
        ctx = build_context(now - timedelta(hours=1), now)
        results = run_rollup("kill_burst", ctx)
        self.assertTrue(results)
        self.assertEqual(results[0].kind, "killmail_batch")
