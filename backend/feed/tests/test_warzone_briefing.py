from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from feed.constants import FACTION_AMARR
from feed.helpers.warzone_briefing import build_warzone_briefing
from feed.management.commands.seed_feed_monitored_systems import (
    seed_from_fixture,
)
from feed.models import FeedKillmail, FeedSystemContestedSnapshot


class WarzoneBriefingTestCase(TestCase):
    def setUp(self):
        seed_from_fixture()
        self.now = timezone.now().replace(minute=50, second=0, microsecond=0)
        self.huola_id = 30003067
        self.vard_id = 30002538

    def _snapshot(
        self,
        system_id: int,
        contested_percent: float,
        *,
        captured_at,
        occupier_faction_id=500002,
    ) -> None:
        FeedSystemContestedSnapshot.objects.create(
            solar_system_id=system_id,
            contested_percent=contested_percent,
            occupier_faction_id=occupier_faction_id,
            victor_faction_id=FACTION_AMARR,
            captured_at=captured_at,
        )

    @patch("feed.helpers.warzone_briefing._resolve_system_metadata")
    def test_build_warzone_briefing_orders_changes_and_cards(
        self, mock_metadata
    ):
        mock_metadata.return_value = {
            self.huola_id: (3800, "minmatar"),
            self.vard_id: (3801, "amarr"),
            30003068: (45032, "minmatar"),
            30004299: (3802, "amarr"),
            30002812: (3798, "amarr"),
        }
        baseline_at = self.now - timedelta(hours=24)
        for system_id, baseline_percent in (
            (self.huola_id, 64.0),
            (self.vard_id, 80.0),
            (30003068, 70.0),
            (30004299, 55.0),
            (30002812, 60.0),
        ):
            self._snapshot(
                system_id, baseline_percent, captured_at=baseline_at
            )
        self._snapshot(self.huola_id, 72.5, captured_at=self.now)
        self._snapshot(self.vard_id, 87.0, captured_at=self.now)
        self._snapshot(30003068, 70.0, captured_at=self.now)
        self._snapshot(30004299, 55.0, captured_at=self.now)
        self._snapshot(30002812, 60.0, captured_at=self.now)

        FeedKillmail.objects.create(
            killmail_id=9001,
            hash="abc",
            killmail_time=self.now - timedelta(hours=2),
            solar_system_id=self.vard_id,
            attacker_summary=[],
            raw_killmail={},
        )
        FeedKillmail.objects.create(
            killmail_id=9002,
            hash="def",
            killmail_time=self.now - timedelta(hours=1),
            solar_system_id=self.vard_id,
            attacker_summary=[],
            raw_killmail={},
        )

        briefing = build_warzone_briefing(now=self.now)

        self.assertTrue(briefing.has_full_24h_window)
        self.assertEqual(briefing.hot_kills.system_id, self.vard_id)
        self.assertEqual(briefing.hot_kills.kills_24h, 2)
        self.assertEqual(len(briefing.changes_24h), 5)
        self.assertEqual(briefing.changes_24h[0].system_id, self.huola_id)
        self.assertEqual(briefing.changes_24h[0].delta_24h, 8.5)
        self.assertEqual(briefing.changes_24h[1].system_id, self.vard_id)
        self.assertEqual(briefing.changes_24h[1].delta_24h, 7.0)

    @patch("feed.helpers.warzone_briefing._resolve_system_metadata")
    def test_single_snapshot_shows_zero_delta_in_changes(self, mock_metadata):
        mock_metadata.return_value = {self.huola_id: (3800, "minmatar")}
        self._snapshot(self.huola_id, 72.0, captured_at=self.now)

        briefing = build_warzone_briefing(now=self.now)

        self.assertFalse(briefing.has_full_24h_window)
        self.assertEqual(len(briefing.changes_24h), 1)
        self.assertEqual(briefing.changes_24h[0].delta_24h, 0.0)
        self.assertEqual(len(briefing.minmatar_contested), 1)

    @patch("feed.helpers.warzone_briefing._resolve_system_metadata")
    def test_partial_window_uses_oldest_snapshot_in_range(self, mock_metadata):
        mock_metadata.return_value = {
            self.huola_id: (3800, "minmatar"),
            self.vard_id: (3801, "amarr"),
        }
        self._snapshot(
            self.huola_id, 64.0, captured_at=self.now - timedelta(hours=3)
        )
        self._snapshot(self.huola_id, 72.0, captured_at=self.now)
        self._snapshot(
            self.vard_id, 80.0, captured_at=self.now - timedelta(hours=2)
        )
        self._snapshot(self.vard_id, 85.0, captured_at=self.now)

        briefing = build_warzone_briefing(now=self.now)

        self.assertFalse(briefing.has_full_24h_window)
        huola = next(
            r for r in briefing.changes_24h if r.system_id == self.huola_id
        )
        vard = next(
            r for r in briefing.changes_24h if r.system_id == self.vard_id
        )
        self.assertEqual(huola.delta_24h, 8.0)
        self.assertEqual(vard.delta_24h, 5.0)

    @patch("feed.helpers.warzone_briefing._resolve_system_metadata")
    def test_contested_cards_require_partial_contest(self, mock_metadata):
        mock_metadata.return_value = {
            self.huola_id: (3800, "minmatar"),
            self.vard_id: (3801, "amarr"),
        }
        baseline_at = self.now - timedelta(hours=24)
        self._snapshot(self.huola_id, 50.0, captured_at=baseline_at)
        self._snapshot(self.vard_id, 0.0, captured_at=baseline_at)
        self._snapshot(self.huola_id, 72.0, captured_at=self.now)
        self._snapshot(self.vard_id, 100.0, captured_at=self.now)

        briefing = build_warzone_briefing(now=self.now)

        self.assertEqual(len(briefing.minmatar_contested), 1)
        self.assertEqual(
            briefing.minmatar_contested[0].system_id, self.huola_id
        )
        self.assertEqual(briefing.amarr_contested, [])
