"""Tests for occurred_at backfill helpers."""

from datetime import date, datetime, time

from django.utils import timezone

from app.test import TestCase
from eveonline.models import EveCharacter, EveCharacterMiningEntry
from eveuniverse.models import EveCategory, EveGroup, EveType
from tribes.management.commands.backfill_tribe_activity_occurred_at import (
    _occurred_at_mining,
)


class OccurredAtMiningTestCase(TestCase):
    def setUp(self):
        super().setUp()
        now = timezone.now()
        category, _ = EveCategory.objects.get_or_create(
            id=99002,
            defaults={
                "name": "Test Category",
                "last_updated": now,
                "published": True,
            },
        )
        group, _ = EveGroup.objects.get_or_create(
            id=99002,
            defaults={
                "name": "Test Group",
                "last_updated": now,
                "published": True,
                "eve_category": category,
            },
        )
        ore, _ = EveType.objects.get_or_create(
            id=1228,
            defaults={
                "name": "Scordite",
                "last_updated": now,
                "published": True,
                "eve_group": group,
                "volume": 0.15,
            },
        )
        self.character = EveCharacter.objects.create(
            character_id=7002,
            character_name="Backfill Miner",
        )
        self.entry = EveCharacterMiningEntry.objects.create(
            character=self.character,
            eve_type=ore,
            date=date(2026, 6, 14),
            quantity=100,
            solar_system_id=30000142,
        )

    def test_parses_reference_id_with_hyphenated_date(self):
        ref_id = (
            f"{self.entry.character_id}-{self.entry.eve_type_id}-"
            f"{self.entry.date}-{self.entry.solar_system_id}"
        )
        occurred_at = _occurred_at_mining(ref_id)
        self.assertEqual(
            occurred_at,
            timezone.make_aware(datetime.combine(self.entry.date, time.min)),
        )
