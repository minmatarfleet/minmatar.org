from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from django.test import TestCase
from django.utils import timezone as dj_timezone

from feed.helpers.clusters import detect_clusters
from feed.helpers.ingest import upsert_feed_killmail_from_r2z2
from feed.management.commands.seed_feed_monitored_systems import (
    seed_from_fixture,
)
from feed.models import (
    FeedCluster,
    FeedEvent,
    FeedEventKillmailLink,
    FeedKillmail,
)
from feed.rollups.registry import build_context, run_rollup
from feed.rollups.writer import write_rollup_results
from feed.tests.helpers import make_killmail_payload

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "engagement_vard_136398967"
ANCHOR_TIME = datetime(2026, 6, 19, 17, 25, 8, tzinfo=timezone.utc)


class GoldenEngagementTestCase(TestCase):
    def setUp(self):
        seed_from_fixture()
        anchor_path = FIXTURE_DIR / "killmail_136398967.json"
        anchor = json.loads(anchor_path.read_text())
        upsert_feed_killmail_from_r2z2(anchor)

        for i in range(6):
            offset = timedelta(minutes=i * 2)
            payload = make_killmail_payload(
                136398900 + i,
                killmail_time=ANCHOR_TIME - timedelta(minutes=10) + offset,
                attacker_count=8,
            )
            upsert_feed_killmail_from_r2z2(payload)

    def test_engagement_produces_fleet_cluster_and_event(self):
        detect_clusters(since_hours=72)
        fleet_clusters = FeedCluster.objects.filter(
            cluster_type=FeedCluster.ClusterType.FLEET_ENGAGEMENT,
            solar_system_id=30002538,
        )
        self.assertTrue(fleet_clusters.exists())
        cluster = fleet_clusters.first()
        self.assertGreaterEqual(cluster.kill_count, 5)
        self.assertGreaterEqual(cluster.pilot_count, 8)
        self.assertIn(136398967, cluster.killmail_ids)

        now = dj_timezone.now()
        ctx = build_context(now - timedelta(hours=72), now)
        results = run_rollup("fleet_active", ctx)
        write_rollup_results(results)

        events = FeedEvent.objects.filter(kind=FeedEvent.Kind.FLEET_ACTIVE)
        self.assertTrue(events.exists())
        event = events.first()
        self.assertEqual(event.payload.get("faction"), "minmatar")
        self.assertEqual(event.accent, FeedEvent.Accent.MILITIA)

        anchor = FeedKillmail.objects.get(killmail_id=136398967)
        self.assertTrue(
            FeedEventKillmailLink.objects.filter(
                feed_event=event, feed_killmail=anchor
            ).exists()
        )
