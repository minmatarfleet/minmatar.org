from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from django.test import TestCase

from feed.helpers.zkill_backfill import backfill_monitored_systems
from feed.management.commands.seed_feed_monitored_systems import (
    seed_from_fixture,
)
from feed.models import FeedKillmail, FeedMonitoredSystem


class ZkillBackfillTestCase(TestCase):
    def setUp(self):
        seed_from_fixture()

    @patch("feed.helpers.zkill_backfill.time.sleep")
    @patch("feed.helpers.zkill_backfill.requests.get")
    def test_backfill_monitored_systems_ingests_recent_kills(
        self, mock_get: MagicMock, mock_sleep: MagicMock
    ):
        del mock_sleep
        kill_time = datetime(2026, 6, 19, 20, 0, 0, tzinfo=timezone.utc)

        def fake_get(url, **kwargs):
            response = MagicMock()
            if "/pastSeconds/" in url:
                if not url.endswith("/page/1/"):
                    response.status_code = 200
                    response.json.return_value = []
                    return response
                response.status_code = 200
                response.json.return_value = [
                    {
                        "killmail_id": 136402789,
                        "zkb": {
                            "hash": "abc123",
                            "npc": False,
                        },
                    }
                ]
                return response
            if "/killmails/136402789/" in url:
                response.status_code = 200
                response.json.return_value = {
                    "killmail_id": 136402789,
                    "killmail_time": kill_time.isoformat().replace(
                        "+00:00", "Z"
                    ),
                    "solar_system_id": 30003067,
                    "victim": {"character_id": 1, "ship_type_id": 670},
                    "attackers": [
                        {
                            "character_id": 2,
                            "faction_id": 500002,
                            "ship_type_id": 670,
                            "damage_done": 100,
                            "final_blow": True,
                        }
                    ],
                }
                return response
            raise AssertionError(f"Unexpected URL: {url}")

        mock_get.side_effect = fake_get

        stats = backfill_monitored_systems(hours=24, sleep_seconds=0)

        self.assertEqual(stats["inserted"], 1)
        self.assertEqual(FeedKillmail.objects.count(), 1)
        self.assertEqual(
            FeedKillmail.objects.get().killmail_id,
            136402789,
        )

    @patch("feed.helpers.zkill_backfill.requests.get")
    def test_backfill_skips_existing_killmails(self, mock_get: MagicMock):
        FeedKillmail.objects.create(
            killmail_id=136402789,
            hash="abc123",
            killmail_time=datetime(2026, 6, 19, 20, 0, 0, tzinfo=timezone.utc),
            solar_system_id=30003067,
            raw_killmail={},
        )

        def fake_get(url, **kwargs):
            response = MagicMock()
            if "/pastSeconds/" in url and url.endswith("/page/1/"):
                response.status_code = 200
                response.json.return_value = [
                    {
                        "killmail_id": 136402789,
                        "zkb": {"hash": "abc123", "npc": False},
                    }
                ]
                return response
            response.status_code = 200
            response.json.return_value = []
            return response

        mock_get.side_effect = fake_get

        stats = backfill_monitored_systems(hours=24, sleep_seconds=0)

        self.assertEqual(stats["skipped_existing"], 5)
        self.assertEqual(stats["inserted"], 0)

    def test_backfill_requires_monitored_systems(self):
        FeedMonitoredSystem.objects.all().delete()
        with self.assertRaises(ValueError):
            backfill_monitored_systems(hours=24, sleep_seconds=0)
