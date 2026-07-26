"""Tests for blueprint ME/TE defaults and navy/faction hull detection."""

from django.test import TestCase
from eveuniverse.models import (
    EveCategory,
    EveDogmaAttribute,
    EveGroup,
    EveType,
    EveTypeDogmaAttribute,
)

from industry.helpers.blueprint_efficiency import (
    DOGMA_META_GROUP_ID,
    META_GROUP_FACTION,
    default_blueprint_me_te_percent,
    is_faction_navy_hull,
)


class BlueprintEfficiencyTestCase(TestCase):
    def setUp(self):
        self.ship_cat, _ = EveCategory.objects.get_or_create(
            id=6, defaults={"name": "Ship", "published": True}
        )
        self.material_cat, _ = EveCategory.objects.get_or_create(
            id=4, defaults={"name": "Material", "published": True}
        )
        self.bs_group, _ = EveGroup.objects.get_or_create(
            id=27,
            defaults={
                "name": "Battleship",
                "published": True,
                "eve_category": self.ship_cat,
            },
        )
        self.mineral_group, _ = EveGroup.objects.get_or_create(
            id=18,
            defaults={
                "name": "Mineral",
                "published": True,
                "eve_category": self.material_cat,
            },
        )
        EveDogmaAttribute.objects.get_or_create(
            id=DOGMA_META_GROUP_ID,
            defaults={
                "name": "metaGroupID",
                "published": True,
                "default_value": 0.0,
                "description": "meta group",
                "display_name": "Meta Group",
                "high_is_good": False,
                "stackable": True,
            },
        )

    def test_tech_i_hull_defaults_to_10_20(self):
        hull = EveType.objects.create(
            id=901001,
            name="Plan Typhoon",
            published=True,
            eve_group=self.bs_group,
        )
        self.assertFalse(is_faction_navy_hull(hull))
        self.assertEqual(default_blueprint_me_te_percent(hull), (10.0, 20.0))

    def test_navy_name_suffix_defaults_to_0_0(self):
        hull = EveType.objects.create(
            id=901002,
            name="Apocalypse Navy Issue",
            published=True,
            eve_group=self.bs_group,
        )
        self.assertTrue(is_faction_navy_hull(hull))
        self.assertEqual(default_blueprint_me_te_percent(hull), (0.0, 0.0))

    def test_fleet_issue_name_defaults_to_0_0(self):
        hull = EveType.objects.create(
            id=901003,
            name="Stabber Fleet Issue",
            published=True,
            eve_group=self.bs_group,
        )
        self.assertTrue(is_faction_navy_hull(hull))
        self.assertEqual(default_blueprint_me_te_percent(hull), (0.0, 0.0))

    def test_faction_meta_group_dogma_defaults_to_0_0(self):
        hull = EveType.objects.create(
            id=901004,
            name="Dramiel",
            published=True,
            eve_group=self.bs_group,
        )
        EveTypeDogmaAttribute.objects.create(
            eve_type=hull,
            eve_dogma_attribute_id=DOGMA_META_GROUP_ID,
            value=META_GROUP_FACTION,
        )
        self.assertTrue(is_faction_navy_hull(hull))
        self.assertEqual(default_blueprint_me_te_percent(hull), (0.0, 0.0))

    def test_non_ship_faction_name_ignored(self):
        material = EveType.objects.create(
            id=901005,
            name="Fake Navy Issue",
            published=True,
            eve_group=self.mineral_group,
        )
        self.assertFalse(is_faction_navy_hull(material))
        self.assertEqual(
            default_blueprint_me_te_percent(material), (10.0, 20.0)
        )
