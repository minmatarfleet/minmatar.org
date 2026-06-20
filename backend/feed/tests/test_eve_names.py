from __future__ import annotations

from django.test import TestCase
from eveuniverse.models import EveCategory, EveGroup, EveType

from feed.helpers.eve_names import (
    detect_formation_type,
    top_hull_classes_from_counts,
    top_ships_from_counts,
    without_capsule_ship_counts,
)


class EveNamesTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ship_category, _ = EveCategory.objects.get_or_create(
            id=6,
            defaults={"name": "Ship", "published": True},
        )
        capsule_group, _ = EveGroup.objects.get_or_create(
            id=29,
            defaults={
                "name": "Capsule",
                "published": True,
                "eve_category": ship_category,
            },
        )
        cruiser_group, _ = EveGroup.objects.get_or_create(
            id=26,
            defaults={
                "name": "Cruiser",
                "published": True,
                "eve_category": ship_category,
            },
        )
        EveType.objects.get_or_create(
            id=670,
            defaults={
                "name": "Capsule",
                "published": True,
                "eve_group": capsule_group,
            },
        )
        EveType.objects.get_or_create(
            id=22468,
            defaults={
                "name": "Rupture",
                "published": True,
                "eve_group": cruiser_group,
            },
        )

    def test_without_capsule_ship_counts(self):
        filtered = without_capsule_ship_counts({"670": 12, "22468": 3})
        self.assertEqual(filtered, {"22468": 3})

    def test_top_ships_skips_capsules(self):
        ships = top_ships_from_counts({"670": 12, "22468": 3})
        self.assertEqual(len(ships), 1)
        self.assertEqual(ships[0]["type_id"], 22468)

    def test_top_hull_classes_skips_capsules(self):
        classes = top_hull_classes_from_counts({"670": 12, "22468": 3})
        self.assertEqual(classes, ["cruisers"])

    def test_detect_formation_type_fleet_from_dominant_ship(self):
        self.assertEqual(
            detect_formation_type({"22468": 5, "11198": 1}),
            "fleet",
        )

    def test_detect_formation_type_gang_from_even_mix(self):
        self.assertEqual(
            detect_formation_type({"22468": 2, "11198": 2, "33333": 2}),
            "gang",
        )

    def test_detect_formation_type_gang_without_counts(self):
        self.assertEqual(detect_formation_type(None), "gang")
        self.assertEqual(detect_formation_type({}), "gang")
