from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from feed.rollups.engagement_copy import (
    build_militia_engagement_copy,
    build_warzone_engagement_copy,
)


class EngagementCopyTestCase(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.started = self.now - timedelta(minutes=12)

    def test_small_skirmish_title(self):
        copy = build_warzone_engagement_copy(
            system="Auga",
            kills=9,
            pilots=7,
            started_at=self.started,
            last_kill_at=self.now,
        )
        self.assertEqual(copy.tier, "small")
        self.assertEqual(copy.title, "Small skirmish in Auga")
        self.assertIn("9 kills", copy.subheader)
        self.assertIn("7 pilots", copy.subheader)

    def test_large_skirmish_from_kill_count(self):
        copy = build_warzone_engagement_copy(
            system="Huola",
            kills=24,
            pilots=10,
            started_at=self.started,
            last_kill_at=self.now,
        )
        self.assertEqual(copy.tier, "large")
        self.assertEqual(copy.title, "Large skirmish in Huola")

    def test_major_engagement_from_pilot_count(self):
        copy = build_warzone_engagement_copy(
            system="Kourmonen",
            kills=18,
            pilots=42,
            started_at=self.started,
            last_kill_at=self.now,
        )
        self.assertEqual(copy.tier, "major")
        self.assertEqual(copy.title, "Major engagement in Kourmonen")

    def test_preview_includes_top_ships(self):
        copy = build_warzone_engagement_copy(
            system="Auga",
            kills=20,
            pilots=15,
            started_at=self.started,
            last_kill_at=self.now,
            ship_counts={"22468": 4, "11198": 2},
        )
        self.assertIn("22468", copy.preview)

    def test_militia_fleet_engagement_title(self):
        copy = build_militia_engagement_copy(
            faction_label="Minmatar",
            system="Auga",
            kills=25,
            pilots=20,
            started_at=self.started,
            last_kill_at=self.now,
        )
        self.assertEqual(copy.tier, "large")
        self.assertEqual(copy.title, "Minmatar fleet engagement")

    def test_militia_major_operation(self):
        copy = build_militia_engagement_copy(
            faction_label="Amarr",
            system="Huola",
            kills=55,
            pilots=48,
            started_at=self.started,
            last_kill_at=self.now,
        )
        self.assertEqual(copy.tier, "major")
        self.assertEqual(copy.title, "Major Amarr operation")
