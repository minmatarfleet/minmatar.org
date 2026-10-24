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


class FeedHidesMembersOnlyFleetsTestCase(TestCase):
    """A members-only tribe fleet must not show up in the public feed."""

    def _fleet_kills_card(self, fleet, title):
        return FeedEvent.objects.create(
            kind=FeedEvent.Kind.FLEET_KILLS,
            occurred_at=timezone.now(),
            title=title,
            accent=FeedEvent.Accent.COMBAT,
            rollup_code="fleet_kills",
            cluster_key=f"fleet_kills:{fleet.id}",
            payload={"fleet_id": fleet.id},
        )

    def test_members_only_group_fleet_card_is_hidden(self):
        # pylint: disable=import-outside-toplevel
        from fleets.models import EveFleet
        from tribes.models import Tribe, TribeGroup

        tribe = Tribe.objects.create(name="Capitals", slug="capitals")
        group = TribeGroup.objects.create(tribe=tribe, name="Dreads")
        start = timezone.now() - timedelta(hours=1)
        alliance = EveFleet.objects.create(type="training", start_time=start)
        hidden = EveFleet.objects.create(
            type="training", start_time=start, host_group=group
        )
        open_fleet = EveFleet.objects.create(
            type="training",
            start_time=start,
            host_group=group,
            open_to_alliance=True,
        )
        self._fleet_kills_card(alliance, "alliance card")
        self._fleet_kills_card(hidden, "members-only card")
        self._fleet_kills_card(open_fleet, "open card")

        titles = [
            item["title"]
            for item in Client().get("/api/feed/").json()["items"]
        ]
        self.assertIn("alliance card", titles)
        self.assertIn("open card", titles)
        self.assertNotIn("members-only card", titles)
