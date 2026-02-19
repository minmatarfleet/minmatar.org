"""Tests for mining producers in industry.helpers.producers."""

import factory
from datetime import timedelta

from django.db.models import signals
from django.utils import timezone

from app.test import TestCase
from eveuniverse.models import EveCategory, EveGroup, EveType, EveTypeMaterial
from eveonline.models import EveCharacter
from eveonline.models.characters import EveCharacterMiningEntry
from industry.helpers.producers import (
    get_mining_producers_for_type,
    get_producers_for_types,
)


def _ensure_eve_types(type_ids):
    now = timezone.now()
    category, _ = EveCategory.objects.get_or_create(
        id=9999,
        defaults={"name": "Test", "last_updated": now, "published": True},
    )
    group, _ = EveGroup.objects.get_or_create(
        id=9999,
        defaults={
            "name": "Test",
            "last_updated": now,
            "published": True,
            "eve_category": category,
        },
    )
    created = {}
    for tid, name in type_ids.items():
        et, _ = EveType.objects.get_or_create(
            id=tid,
            defaults={
                "name": name,
                "last_updated": now,
                "eve_group": group,
                "published": True,
            },
        )
        created[tid] = et
    return created


class MiningProducersTest(TestCase):

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def setUp(self):
        super().setUp()
        self.types = _ensure_eve_types(
            {
                34: "Tritanium",
                35: "Pyerite",
                1228: "Scordite",
                22: "Arkonor",
            }
        )
        # Scordite reprocesses into Tritanium + Pyerite
        EveTypeMaterial.objects.create(
            eve_type=self.types[1228],
            material_eve_type=self.types[34],
            quantity=150,
        )
        EveTypeMaterial.objects.create(
            eve_type=self.types[1228],
            material_eve_type=self.types[35],
            quantity=99,
        )
        # Arkonor reprocesses into Pyerite
        EveTypeMaterial.objects.create(
            eve_type=self.types[22],
            material_eve_type=self.types[35],
            quantity=3200,
        )

        self.miner = EveCharacter.objects.create(
            character_id=7001,
            character_name="Test Miner",
        )
        today = timezone.now().date()
        EveCharacterMiningEntry.objects.create(
            character=self.miner,
            eve_type=self.types[1228],
            date=today - timedelta(days=5),
            quantity=100_000,
            solar_system_id=30001,
        )
        EveCharacterMiningEntry.objects.create(
            character=self.miner,
            eve_type=self.types[22],
            date=today - timedelta(days=3),
            quantity=200_000,
            solar_system_id=30001,
        )

    def test_mining_producers_for_mineral(self):
        """Tritanium: Scordite reprocesses into it, so our miner shows up."""
        results = get_mining_producers_for_type(34)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["character_id"], 7001)
        self.assertEqual(results[0]["character_name"], "Test Miner")
        self.assertEqual(results[0]["total_quantity"], 100_000)

    def test_mining_producers_aggregates_multiple_ores(self):
        """Pyerite: both Scordite and Arkonor produce it, quantities sum."""
        results = get_mining_producers_for_type(35)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["total_quantity"], 300_000)

    def test_mining_producers_direct_ore(self):
        """Direct lookup for the ore type itself."""
        results = get_mining_producers_for_type(1228)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["total_quantity"], 100_000)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_mining_producers_excludes_old_entries(self):
        """Entries older than 30 days are excluded."""
        old_date = timezone.now().date() - timedelta(days=45)
        old_miner = EveCharacter.objects.create(
            character_id=7002,
            character_name="Old Miner",
        )
        EveCharacterMiningEntry.objects.create(
            character=old_miner,
            eve_type=self.types[1228],
            date=old_date,
            quantity=99999,
            solar_system_id=30001,
        )
        results = get_mining_producers_for_type(34)
        cids = {r["character_id"] for r in results}
        self.assertNotIn(7002, cids)

    def test_batch_includes_mining_in_character_producers(self):
        """get_producers_for_types merges miners into character_producers."""
        result = get_producers_for_types([34])
        self.assertIn("character_producers", result[34])
        char_producers = result[34]["character_producers"]
        self.assertEqual(len(char_producers), 1)
        self.assertEqual(char_producers[0]["id"], 7001)
        self.assertIn("total_value_isk", char_producers[0])

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_ore_ignores_mineral_below_25_percent(self):
        """Ore only counts for a mineral if that mineral is >= 25% of the ore."""
        # Ore 9999: Tritanium 10%, Pyerite 90% (total 100)
        self.types[9999] = EveType.objects.get_or_create(
            id=9999,
            defaults={
                "name": "Minor Ore",
                "last_updated": timezone.now(),
                "eve_group": self.types[1228].eve_group,
                "published": True,
            },
        )[0]
        EveTypeMaterial.objects.create(
            eve_type=self.types[9999],
            material_eve_type=self.types[34],
            quantity=10,
        )
        EveTypeMaterial.objects.create(
            eve_type=self.types[9999],
            material_eve_type=self.types[35],
            quantity=90,
        )
        minor_miner = EveCharacter.objects.create(
            character_id=7010,
            character_name="Minor Ore Miner",
        )
        EveCharacterMiningEntry.objects.create(
            character=minor_miner,
            eve_type=self.types[9999],
            date=timezone.now().date(),
            quantity=10000,
            solar_system_id=30001,
        )
        # Tritanium (34): 10% < 25% so mining this ore should NOT count
        results_34 = get_mining_producers_for_type(34)
        cids_34 = {r["character_id"] for r in results_34}
        self.assertNotIn(7010, cids_34)
        # Pyerite (35): 90% >= 25% so mining this ore should count
        results_35 = get_mining_producers_for_type(35)
        cids_35 = {r["character_id"] for r in results_35}
        self.assertIn(7010, cids_35)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_ordered_by_value_then_quantity(self):
        """Miners are returned ordered by total_value_isk then total_quantity descending."""
        big_miner = EveCharacter.objects.create(
            character_id=7003,
            character_name="Big Miner",
        )
        EveCharacterMiningEntry.objects.create(
            character=big_miner,
            eve_type=self.types[1228],
            date=timezone.now().date(),
            quantity=999_999,
            solar_system_id=30001,
        )
        results = get_mining_producers_for_type(34)
        self.assertEqual(len(results), 2)
        # With no market prices, order is by quantity (secondary sort)
        self.assertEqual(results[0]["character_id"], 7003)
        self.assertEqual(results[1]["character_id"], 7001)
        self.assertIn("total_value_isk", results[0])
