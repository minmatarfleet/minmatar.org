"""Tests for Market Ops item type + variant classification."""

from django.test import TestCase
from eveuniverse.models import (
    EveCategory,
    EveDogmaAttribute,
    EveDogmaEffect,
    EveGroup,
    EveType,
    EveTypeDogmaAttribute,
    EveTypeDogmaEffect,
)

from market.helpers.item_classification import (
    DOGMA_META_GROUP_ID,
    DOGMA_TECH_LEVEL_ID,
    EFFECT_HI_POWER,
    EFFECT_LO_POWER,
    EFFECT_MED_POWER,
    EFFECT_RIG_SLOT,
    ITEM_TYPE_CONSUMABLE,
    ITEM_TYPE_DRONE,
    ITEM_TYPE_HIGH_SLOT,
    ITEM_TYPE_HULL,
    ITEM_TYPE_LOW_SLOT,
    ITEM_TYPE_MEDIUM_SLOT,
    ITEM_TYPE_OTHER,
    ITEM_TYPE_RIG,
    ITEM_VARIANT_DEADSPACE,
    ITEM_VARIANT_FACTION,
    ITEM_VARIANT_OTHER,
    ITEM_VARIANT_T1,
    ITEM_VARIANT_T2,
    META_GROUP_DEADSPACE,
    META_GROUP_FACTION,
    META_GROUP_OFFICER,
    META_GROUP_STORYLINE,
    classify_items,
)


class ItemClassificationTestCase(TestCase):
    def setUp(self):
        self.ship_cat, _ = EveCategory.objects.get_or_create(
            id=6, defaults={"name": "Ship", "published": True}
        )
        self.module_cat, _ = EveCategory.objects.get_or_create(
            id=7, defaults={"name": "Module", "published": True}
        )
        self.charge_cat, _ = EveCategory.objects.get_or_create(
            id=8, defaults={"name": "Charge", "published": True}
        )
        self.drone_cat, _ = EveCategory.objects.get_or_create(
            id=18, defaults={"name": "Drone", "published": True}
        )
        self.subsystem_cat, _ = EveCategory.objects.get_or_create(
            id=32, defaults={"name": "Subsystem", "published": True}
        )

        self.frig, _ = EveGroup.objects.get_or_create(
            id=25,
            defaults={
                "name": "Frigate",
                "published": True,
                "eve_category": self.ship_cat,
            },
        )
        self.prop, _ = EveGroup.objects.get_or_create(
            id=46,
            defaults={
                "name": "Propulsion Module",
                "published": True,
                "eve_category": self.module_cat,
            },
        )
        self.weapon, _ = EveGroup.objects.get_or_create(
            id=74,
            defaults={
                "name": "Hybrid Weapon",
                "published": True,
                "eve_category": self.module_cat,
            },
        )
        self.armor, _ = EveGroup.objects.get_or_create(
            id=55,
            defaults={
                "name": "Armor Reinforcer",
                "published": True,
                "eve_category": self.module_cat,
            },
        )
        self.rig, _ = EveGroup.objects.get_or_create(
            id=773,
            defaults={
                "name": "Rig Armor",
                "published": True,
                "eve_category": self.module_cat,
            },
        )
        self.charge_grp, _ = EveGroup.objects.get_or_create(
            id=83,
            defaults={
                "name": "Hybrid Charge",
                "published": True,
                "eve_category": self.charge_cat,
            },
        )
        self.drone_grp, _ = EveGroup.objects.get_or_create(
            id=100,
            defaults={
                "name": "Combat Drone",
                "published": True,
                "eve_category": self.drone_cat,
            },
        )
        self.subsystem_grp, _ = EveGroup.objects.get_or_create(
            id=958,
            defaults={
                "name": "Defensive Subsystem",
                "published": True,
                "eve_category": self.subsystem_cat,
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
        EveDogmaAttribute.objects.get_or_create(
            id=DOGMA_TECH_LEVEL_ID,
            defaults={
                "name": "techLevel",
                "published": True,
                "default_value": 1.0,
                "description": "tech level",
                "display_name": "Tech Level",
                "high_is_good": True,
                "stackable": True,
            },
        )
        for effect_id, name in (
            (EFFECT_HI_POWER, "hiPower"),
            (EFFECT_MED_POWER, "medPower"),
            (EFFECT_LO_POWER, "loPower"),
            (EFFECT_RIG_SLOT, "rigSlot"),
        ):
            EveDogmaEffect.objects.get_or_create(
                id=effect_id,
                defaults={
                    "name": name,
                    "display_name": name,
                    "description": name,
                    "published": True,
                },
            )

    def test_classifies_type_and_variant(self):
        t1_hull = EveType.objects.create(
            id=920001, name="Rifter", published=True, eve_group=self.frig
        )
        t2_hull = EveType.objects.create(
            id=920002, name="Hawk", published=True, eve_group=self.frig
        )
        EveTypeDogmaAttribute.objects.create(
            eve_type=t2_hull,
            eve_dogma_attribute_id=DOGMA_TECH_LEVEL_ID,
            value=2.0,
        )
        faction_hull = EveType.objects.create(
            id=920003,
            name="Dramiel",
            published=True,
            eve_group=self.frig,
        )
        EveTypeDogmaAttribute.objects.create(
            eve_type=faction_hull,
            eve_dogma_attribute_id=DOGMA_META_GROUP_ID,
            value=META_GROUP_FACTION,
        )
        navy_hull = EveType.objects.create(
            id=920004,
            name="Catalyst Navy Issue",
            published=True,
            eve_group=self.frig,
        )
        high_t2 = EveType.objects.create(
            id=920005,
            name="Heavy Neutron Blaster II",
            published=True,
            eve_group=self.weapon,
        )
        EveTypeDogmaEffect.objects.create(
            eve_type=high_t2,
            eve_dogma_effect_id=EFFECT_HI_POWER,
            is_default=False,
        )
        EveTypeDogmaAttribute.objects.create(
            eve_type=high_t2,
            eve_dogma_attribute_id=DOGMA_TECH_LEVEL_ID,
            value=2.0,
        )
        mid = EveType.objects.create(
            id=920006,
            name="1MN Afterburner I",
            published=True,
            eve_group=self.prop,
        )
        EveTypeDogmaEffect.objects.create(
            eve_type=mid,
            eve_dogma_effect_id=EFFECT_MED_POWER,
            is_default=False,
        )
        low_deadspace = EveType.objects.create(
            id=920007,
            name="Core X-Type Armor Plate",
            published=True,
            eve_group=self.armor,
        )
        EveTypeDogmaEffect.objects.create(
            eve_type=low_deadspace,
            eve_dogma_effect_id=EFFECT_LO_POWER,
            is_default=False,
        )
        EveTypeDogmaAttribute.objects.create(
            eve_type=low_deadspace,
            eve_dogma_attribute_id=DOGMA_META_GROUP_ID,
            value=META_GROUP_DEADSPACE,
        )
        rig = EveType.objects.create(
            id=920008,
            name="Medium Trimark Armor Pump I",
            published=True,
            eve_group=self.rig,
        )
        EveTypeDogmaEffect.objects.create(
            eve_type=rig,
            eve_dogma_effect_id=EFFECT_RIG_SLOT,
            is_default=False,
        )
        ammo = EveType.objects.create(
            id=920009,
            name="Antimatter Charge S",
            published=True,
            eve_group=self.charge_grp,
        )
        drone = EveType.objects.create(
            id=920010,
            name="Hobgoblin II",
            published=True,
            eve_group=self.drone_grp,
        )
        EveTypeDogmaAttribute.objects.create(
            eve_type=drone,
            eve_dogma_attribute_id=DOGMA_TECH_LEVEL_ID,
            value=2.0,
        )
        subsystem = EveType.objects.create(
            id=920011,
            name="Loki Defensive - Adaptive Shielding",
            published=True,
            eve_group=self.subsystem_grp,
        )

        classified = classify_items(
            [
                t1_hull.id,
                t2_hull.id,
                faction_hull.id,
                navy_hull.id,
                high_t2.id,
                mid.id,
                low_deadspace.id,
                rig.id,
                ammo.id,
                drone.id,
                subsystem.id,
            ]
        )

        self.assertEqual(classified[t1_hull.id].item_type, ITEM_TYPE_HULL)
        self.assertEqual(classified[t1_hull.id].item_variant, ITEM_VARIANT_T1)
        self.assertEqual(classified[t2_hull.id].item_type, ITEM_TYPE_HULL)
        self.assertEqual(classified[t2_hull.id].item_variant, ITEM_VARIANT_T2)
        self.assertEqual(classified[faction_hull.id].item_type, ITEM_TYPE_HULL)
        self.assertEqual(
            classified[faction_hull.id].item_variant, ITEM_VARIANT_FACTION
        )
        self.assertEqual(classified[navy_hull.id].item_type, ITEM_TYPE_HULL)
        self.assertEqual(
            classified[navy_hull.id].item_variant, ITEM_VARIANT_FACTION
        )
        self.assertEqual(classified[high_t2.id].item_type, ITEM_TYPE_HIGH_SLOT)
        self.assertEqual(classified[high_t2.id].item_variant, ITEM_VARIANT_T2)
        self.assertEqual(classified[mid.id].item_type, ITEM_TYPE_MEDIUM_SLOT)
        self.assertEqual(classified[mid.id].item_variant, ITEM_VARIANT_T1)
        self.assertEqual(
            classified[low_deadspace.id].item_type, ITEM_TYPE_LOW_SLOT
        )
        self.assertEqual(
            classified[low_deadspace.id].item_variant, ITEM_VARIANT_DEADSPACE
        )
        self.assertEqual(classified[rig.id].item_type, ITEM_TYPE_RIG)
        self.assertEqual(classified[ammo.id].item_type, ITEM_TYPE_CONSUMABLE)
        self.assertEqual(classified[drone.id].item_type, ITEM_TYPE_DRONE)
        self.assertEqual(classified[drone.id].item_variant, ITEM_VARIANT_T2)
        self.assertEqual(classified[subsystem.id].item_type, ITEM_TYPE_OTHER)

    def test_empty_input(self):
        self.assertEqual(classify_items([]), {})

    def test_officer_and_storyline_are_other(self):
        officer = EveType.objects.create(
            id=920020,
            name="Chelm's Modified Adaptive Nano Plating",
            published=True,
            eve_group=self.armor,
        )
        EveTypeDogmaAttribute.objects.create(
            eve_type=officer,
            eve_dogma_attribute_id=DOGMA_META_GROUP_ID,
            value=META_GROUP_OFFICER,
        )
        EveTypeDogmaAttribute.objects.create(
            eve_type=officer,
            eve_dogma_attribute_id=DOGMA_TECH_LEVEL_ID,
            value=1.0,
        )
        storyline = EveType.objects.create(
            id=920021,
            name="Inherent Implants 'Lancer' Small Energy Turret",
            published=True,
            eve_group=self.weapon,
        )
        EveTypeDogmaAttribute.objects.create(
            eve_type=storyline,
            eve_dogma_attribute_id=DOGMA_META_GROUP_ID,
            value=META_GROUP_STORYLINE,
        )
        EveTypeDogmaAttribute.objects.create(
            eve_type=storyline,
            eve_dogma_attribute_id=DOGMA_TECH_LEVEL_ID,
            value=1.0,
        )

        classified = classify_items([officer.id, storyline.id])
        self.assertEqual(
            classified[officer.id].item_variant, ITEM_VARIANT_OTHER
        )
        self.assertEqual(
            classified[storyline.id].item_variant, ITEM_VARIANT_OTHER
        )
