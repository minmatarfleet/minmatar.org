"""Tests for mining producers in industry.helpers.producers."""

import factory
from datetime import timedelta

from django.db.models import signals
from django.utils import timezone

from app.test import TestCase
from eveuniverse.models import (
    EveCategory,
    EveGroup,
    EveType,
    EveTypeMaterial,
    EveMarketPrice,
)
from eveonline.models import EveCharacter
from eveonline.models.characters import EveCharacterMiningEntry
from industry.helpers.producers import (
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

    def test_batch_includes_mining_in_character_producers(self):
        """get_producers_for_types merges miners into character_producers (when value >= 50M)."""
        # Miner has 100k Scordite -> ~60k Tritanium (150/249). Price 1000 -> ~60M ISK
        EveMarketPrice.objects.update_or_create(
            eve_type=self.types[34],
            defaults={"adjusted_price": 1000.0, "average_price": 1000.0},
        )
        result = get_producers_for_types([34])
        self.assertIn("character_producers", result[34])
        char_producers = result[34]["character_producers"]
        self.assertEqual(len(char_producers), 1)
        self.assertEqual(char_producers[0]["id"], 7001)
        self.assertIn("total_value_isk", char_producers[0])
        self.assertGreaterEqual(
            char_producers[0]["total_value_isk"], 50_000_000
        )
