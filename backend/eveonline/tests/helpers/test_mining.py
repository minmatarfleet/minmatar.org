"""Tests for eveonline.helpers.characters.mining – update_character_mining."""

import factory
from datetime import date
from unittest.mock import patch, MagicMock

from django.db.models import signals
from django.utils import timezone

from app.test import TestCase
from eveuniverse.models import EveCategory, EveGroup, EveType
from eveonline.client import EsiClient, EsiResponse
from eveonline.models import EveCharacter
from eveonline.models.characters import EveCharacterMiningEntry
from eveonline.helpers.characters.mining import update_character_mining

MINING_LEDGER = [
    {
        "date": "2026-02-10",
        "quantity": 5000,
        "solar_system_id": 30002324,
        "type_id": 1228,
    },
    {
        "date": "2026-02-10",
        "quantity": 3000,
        "solar_system_id": 30002324,
        "type_id": 22,
    },
    {
        "date": "2026-02-11",
        "quantity": 8000,
        "solar_system_id": 30002325,
        "type_id": 1228,
    },
]


def _ensure_eve_types(type_ids):
    """Create minimal EveCategory + EveGroup + EveType records for testing."""
    now = timezone.now()
    category, _ = EveCategory.objects.get_or_create(
        id=9999,
        defaults={
            "name": "Test Category",
            "last_updated": now,
            "published": True,
        },
    )
    group, _ = EveGroup.objects.get_or_create(
        id=9999,
        defaults={
            "name": "Test Group",
            "last_updated": now,
            "published": True,
            "eve_category": category,
        },
    )
    created = {}
    for tid in type_ids:
        eve_type, _ = EveType.objects.get_or_create(
            id=tid,
            defaults={
                "name": f"Type {tid}",
                "last_updated": now,
                "eve_group": group,
                "published": True,
            },
        )
        created[tid] = eve_type
    return created


class UpdateCharacterMiningTest(TestCase):
    """Tests for the update_character_mining helper."""

    def setUp(self):
        super().setUp()
        all_type_ids = {1228, 22}
        self.eve_types = _ensure_eve_types(all_type_ids)

    def _patch_get_or_create_esi(self):
        original = EveType.objects.get_or_create_esi

        def fake_get_or_create_esi(*args, **kwargs):
            type_id = kwargs.get("id") or (args[0] if args else None)
            if type_id is not None and type_id in self.eve_types:
                return self.eve_types[type_id], False
            return original(*args, **kwargs)

        return patch.object(
            type(EveType.objects),
            "get_or_create_esi",
            side_effect=fake_get_or_create_esi,
        )

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.helpers.characters.mining._ensure_type_materials")
    @patch("eveonline.helpers.characters.mining.EsiClient")
    def test_creates_mining_entries(self, esi_mock_cls, ensure_mats_mock):
        char = EveCharacter.objects.create(
            character_id=6001,
            character_name="Miner Tester",
        )

        esi = MagicMock(spec=EsiClient)
        esi_mock_cls.return_value = esi
        esi.get_character_mining_ledger.return_value = EsiResponse(
            response_code=0, data=MINING_LEDGER
        )

        with self._patch_get_or_create_esi():
            count = update_character_mining(6001)

        self.assertEqual(count, 3)
        self.assertEqual(
            EveCharacterMiningEntry.objects.filter(character=char).count(), 3
        )

        entry = EveCharacterMiningEntry.objects.get(
            character=char,
            eve_type_id=1228,
            date=date(2026, 2, 10),
            solar_system_id=30002324,
        )
        self.assertEqual(entry.quantity, 5000)

        entry2 = EveCharacterMiningEntry.objects.get(
            character=char,
            eve_type_id=1228,
            date=date(2026, 2, 11),
            solar_system_id=30002325,
        )
        self.assertEqual(entry2.quantity, 8000)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.helpers.characters.mining._ensure_type_materials")
    @patch("eveonline.helpers.characters.mining.EsiClient")
    def test_updates_quantity_on_resync(self, esi_mock_cls, ensure_mats_mock):
        """Re-running with updated quantities updates existing rows."""
        char = EveCharacter.objects.create(
            character_id=6002,
            character_name="Miner Resync",
        )

        esi = MagicMock(spec=EsiClient)
        esi_mock_cls.return_value = esi
        esi.get_character_mining_ledger.return_value = EsiResponse(
            response_code=0, data=MINING_LEDGER
        )

        with self._patch_get_or_create_esi():
            update_character_mining(6002)

        updated_ledger = [
            {
                "date": "2026-02-10",
                "quantity": 9999,
                "solar_system_id": 30002324,
                "type_id": 1228,
            },
        ]
        esi.get_character_mining_ledger.return_value = EsiResponse(
            response_code=0, data=updated_ledger
        )
        with self._patch_get_or_create_esi():
            count = update_character_mining(6002)

        self.assertEqual(count, 1)
        entry = EveCharacterMiningEntry.objects.get(
            character=char,
            eve_type_id=1228,
            date=date(2026, 2, 10),
            solar_system_id=30002324,
        )
        self.assertEqual(entry.quantity, 9999)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.helpers.characters.mining.EsiClient")
    def test_skips_suspended_character(self, esi_mock_cls):
        EveCharacter.objects.create(
            character_id=6003,
            character_name="Suspended Miner",
            esi_suspended=True,
        )

        count = update_character_mining(6003)

        self.assertEqual(count, 0)
        esi_mock_cls.assert_not_called()

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.helpers.characters.mining.EsiClient")
    def test_handles_failed_esi_response(self, esi_mock_cls):
        EveCharacter.objects.create(
            character_id=6004,
            character_name="Miner No Token",
        )

        esi = MagicMock(spec=EsiClient)
        esi_mock_cls.return_value = esi
        esi.get_character_mining_ledger.return_value = EsiResponse(
            response_code=905
        )

        count = update_character_mining(6004)

        self.assertEqual(count, 0)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_returns_zero_for_missing_character(self):
        count = update_character_mining(99999)
        self.assertEqual(count, 0)
