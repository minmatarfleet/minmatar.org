from __future__ import annotations

from datetime import timedelta

from django.test import Client, TestCase
from django.utils import timezone

from feed.management.commands.seed_feed_monitored_systems import (
    seed_from_fixture,
)
from feed.models import FeedEvent


class FeedApiTestCase(TestCase):
    def setUp(self):
        seed_from_fixture()
        FeedEvent.objects.create(
            kind=FeedEvent.Kind.KILLMAIL_BATCH,
            occurred_at=timezone.now(),
            title="10 killmails in 15 min",
            subheader="Vard",
            preview="Heavy fighting",
            body="",
            accent=FeedEvent.Accent.COMBAT,
            rollup_code="kill_burst",
            cluster_key="test:cluster:1",
            payload={"system_name": "Vard"},
        )

    def test_public_feed_list(self):
        response = Client().get("/api/feed/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["title"], "10 killmails in 15 min")

    def test_days_param(self):
        old = FeedEvent.objects.create(
            kind=FeedEvent.Kind.KILLMAIL_BATCH,
            occurred_at=timezone.now() - timedelta(days=10),
            title="Old event",
            subheader="Vard",
            preview="",
            body="",
            accent=FeedEvent.Accent.COMBAT,
            rollup_code="kill_burst",
            cluster_key="test:cluster:old",
            payload={},
        )
        response = Client().get("/api/feed/?days=7")
        titles = [item["title"] for item in response.json()["items"]]
        self.assertNotIn("Old event", titles)

        response = Client().get("/api/feed/?days=30")
        titles = [item["title"] for item in response.json()["items"]]
        self.assertIn("Old event", titles)
        old.delete()

    def test_warzone_briefing_endpoint(self):
        response = Client().get("/api/feed/warzone")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("hot_kills", data)
        self.assertIn("amarr_contested", data)
        self.assertIn("minmatar_contested", data)
        self.assertIn("changes_24h", data)
        self.assertIn("has_full_24h_window", data)
