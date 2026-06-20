from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from feed.rollups.engagement_copy import (
    build_militia_engagement_copy,
    build_warzone_engagement_copy,
)

SHIP_NAMES = {22468: "Rupture", 11198: "Stabber"}
HULL_CLASSES = ["destroyers", "cruisers"]


class EngagementCopyTestCase(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.started = self.now - timedelta(minutes=12)
        self.type_name_patcher = patch(
            "feed.helpers.eve_names.resolve_type_names",
            return_value=SHIP_NAMES,
        )
        self.hull_class_patcher = patch(
            "feed.helpers.eve_names.top_hull_classes_from_counts",
            return_value=HULL_CLASSES,
        )
        self.type_name_patcher.start()
        self.hull_class_patcher.start()

    def tearDown(self):
        self.hull_class_patcher.stop()
        self.type_name_patcher.stop()

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

    def test_preview_uses_hull_classes(self):
        copy = build_warzone_engagement_copy(
            system="Auga",
            kills=20,
            pilots=15,
            started_at=self.started,
            last_kill_at=self.now,
            ship_counts={"22468": 4, "11198": 2},
        )
        self.assertEqual(
            copy.preview,
            "Medium skirmish involving destroyers and cruisers.",
        )
        self.assertNotIn("Rupture", copy.preview)
        self.assertNotIn("22468", copy.preview)
        self.assertEqual(copy.payload_extra["ships"][0]["name"], "Rupture")
        self.assertEqual(copy.payload_extra["ships"][0]["count"], 4)

    def test_militia_fleet_active_title(self):
        copy = build_militia_engagement_copy(
            faction_label="Minmatar",
            system="Auga",
            kills=25,
            pilots=20,
            started_at=self.started,
            last_kill_at=self.now,
            ship_counts={"22468": 4, "11198": 2},
        )
        self.assertEqual(copy.tier, "large")
        self.assertEqual(copy.title, "Large Minmatar fleet active")
        self.assertEqual(
            copy.preview,
            "Large fleet involving destroyers and cruisers.",
        )
        self.assertEqual(copy.payload_extra["formation"], "fleet")

        self.assertEqual(copy.payload_extra["formation"], "fleet")

    def test_militia_gang_active_title(self):
        copy = build_militia_engagement_copy(
            faction_label="Minmatar",
            system="Auga",
            kills=25,
            pilots=20,
            started_at=self.started,
            last_kill_at=self.now,
            ship_counts={"22468": 2, "11198": 2, "33333": 2},
        )
        self.assertEqual(copy.tier, "large")
        self.assertEqual(copy.title, "Large Minmatar gang active")
        self.assertEqual(
            copy.preview,
            "Large gang involving destroyers and cruisers.",
        )
        self.assertEqual(copy.payload_extra["formation"], "gang")

    def test_militia_major_fleet_active(self):
        self.hull_class_patcher.stop()
        copy = build_militia_engagement_copy(
            faction_label="Amarr",
            system="Huola",
            kills=55,
            pilots=48,
            started_at=self.started,
            last_kill_at=self.now,
        )
        self.hull_class_patcher.start()
        self.assertEqual(copy.tier, "major")
        self.assertEqual(copy.title, "Major Amarr gang active")
        self.assertEqual(
            copy.preview,
            "Major militia gang active on the front.",
        )
        self.assertEqual(copy.payload_extra["formation"], "gang")

    def test_preview_falls_back_without_ship_counts(self):
        self.hull_class_patcher.stop()
        copy = build_warzone_engagement_copy(
            system="Auga",
            kills=9,
            pilots=7,
            started_at=self.started,
            last_kill_at=self.now,
        )
        self.assertEqual(copy.preview, "Light contact on the front.")
        self.hull_class_patcher.start()
