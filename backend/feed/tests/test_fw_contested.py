from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from feed.constants import FACTION_AMARR
from feed.helpers.fw_contested import (
    contested_percent_from_esi_entry,
    poll_monitored_contested_snapshots,
)
from feed.management.commands.seed_feed_monitored_systems import (
    seed_from_fixture,
)
from feed.models import FeedEvent, FeedSystemContestedSnapshot


class ContestedPercentFromEsiTestCase(TestCase):
    def test_uncontested_system_is_zero_percent(self):
        self.assertEqual(
            contested_percent_from_esi_entry(
                {
                    "contested": "uncontested",
                    "victory_points": 0,
                    "victory_points_threshold": 75000,
                }
            ),
            0.0,
        )

    def test_contested_system_uses_victory_points_ratio(self):
        self.assertEqual(
            contested_percent_from_esi_entry(
                {
                    "contested": "contested",
                    "victory_points": 37500,
                    "victory_points_threshold": 75000,
                }
            ),
            50.0,
        )


class FwContestedPollTestCase(TestCase):
    def setUp(self):
        seed_from_fixture()
        self.system_id = 30003067
        self.now = timezone.now().replace(minute=50, second=0, microsecond=0)

    def _seed_previous_snapshot(self, contested_percent: float) -> None:
        FeedSystemContestedSnapshot.objects.create(
            solar_system_id=self.system_id,
            contested_percent=contested_percent,
            occupier_faction_id=500002,
            victor_faction_id=FACTION_AMARR,
            captured_at=self.now - timedelta(hours=1),
        )

    @patch("feed.helpers.fw_contested.fetch_fw_contested_from_esi")
    def test_first_poll_writes_snapshots_without_events(self, mock_fetch):
        mock_fetch.return_value = {
            self.system_id: MagicMock(
                solar_system_id=self.system_id,
                contested_percent=72.0,
                occupier_faction_id=500002,
                victor_faction_id=FACTION_AMARR,
            )
        }

        stats = poll_monitored_contested_snapshots(now=self.now)

        self.assertEqual(stats["snapshots_written"], 1)
        self.assertEqual(stats["events_written"], 0)
        self.assertFalse(
            FeedEvent.objects.filter(kind="contested_change").exists()
        )

    @patch("feed.helpers.fw_contested.fetch_fw_contested_from_esi")
    def test_poll_writes_feed_event_when_delta_exceeds_threshold(
        self, mock_fetch
    ):
        self._seed_previous_snapshot(64.0)
        mock_fetch.return_value = {
            self.system_id: MagicMock(
                solar_system_id=self.system_id,
                contested_percent=72.5,
                occupier_faction_id=500002,
                victor_faction_id=FACTION_AMARR,
            )
        }

        stats = poll_monitored_contested_snapshots(now=self.now)

        self.assertEqual(stats["snapshots_written"], 1)
        self.assertEqual(stats["events_written"], 1)
        event = FeedEvent.objects.get(kind=FeedEvent.Kind.CONTESTED_CHANGE)
        self.assertIn("Huola", event.title)
        self.assertIn("+8.5%", event.title)
        self.assertEqual(event.payload["delta_percent"], 8.5)
        self.assertEqual(event.payload["contested_percent"], 72.5)
        self.assertEqual(event.payload["previous_contested_percent"], 64.0)
        self.assertEqual(event.rollup_code, "contested_change")

    @patch("feed.helpers.fw_contested.fetch_fw_contested_from_esi")
    def test_poll_skips_event_when_delta_below_threshold(self, mock_fetch):
        self._seed_previous_snapshot(70.0)
        mock_fetch.return_value = {
            self.system_id: MagicMock(
                solar_system_id=self.system_id,
                contested_percent=72.0,
                occupier_faction_id=500002,
                victor_faction_id=FACTION_AMARR,
            )
        }

        stats = poll_monitored_contested_snapshots(now=self.now)

        self.assertEqual(stats["snapshots_written"], 1)
        self.assertEqual(stats["events_written"], 0)

    @patch("feed.helpers.fw_contested.fetch_fw_contested_from_esi")
    def test_poll_upserts_event_for_same_hour(self, mock_fetch):
        self._seed_previous_snapshot(60.0)
        mock_fetch.return_value = {
            self.system_id: MagicMock(
                solar_system_id=self.system_id,
                contested_percent=72.0,
                occupier_faction_id=500002,
                victor_faction_id=FACTION_AMARR,
            )
        }

        poll_monitored_contested_snapshots(now=self.now)
        poll_monitored_contested_snapshots(now=self.now + timedelta(minutes=5))

        self.assertEqual(
            FeedEvent.objects.filter(
                kind=FeedEvent.Kind.CONTESTED_CHANGE
            ).count(),
            1,
        )
