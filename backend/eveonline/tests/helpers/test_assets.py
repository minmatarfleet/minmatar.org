"""Tests for character asset sync helpers."""

from unittest.mock import MagicMock, patch

from django.test import TestCase

from eveonline.helpers.characters.assets import create_character_assets
from eveonline.models import EveCharacter, EveCharacterAsset, EveLocation


def _ship_type(type_id: int, name: str):
    eve_type = MagicMock()
    eve_type.id = type_id
    eve_type.name = name
    eve_type.eve_group.id = 1
    return eve_type


class CreateCharacterAssetsTestCase(TestCase):
    def setUp(self):
        self.character = EveCharacter.objects.create(
            character_id=99001,
            character_name="Test Pilot",
        )
        EveLocation.objects.create(
            location_id=1053229023468,
            location_name="R-6KYM - Casper Anchored It",
            solar_system_id=30002324,
            solar_system_name="R-6KYM",
            short_name="R-6KYM",
        )

    def _asset(self, item_id: int, type_id: int):
        return {
            "is_singleton": True,
            "item_id": item_id,
            "location_flag": "Hangar",
            "location_id": 1053229023468,
            "location_type": "item",
            "quantity": 1,
            "type_id": type_id,
        }

    @patch("eveonline.helpers.characters.assets.EsiClient")
    def test_cached_ship_after_different_ship_uses_correct_type_id(
        self, esi_cls
    ):
        """A cache hit after syncing another hull must not reuse the prior eve_type.id."""
        esi = esi_cls.return_value
        esi.get_eve_type.side_effect = [
            _ship_type(19720, "Revelation"),
            _ship_type(19722, "Naglfar"),
        ]
        eve_group = MagicMock()
        eve_group.eve_category.name = "Ship"
        esi.get_eve_group.return_value = eve_group

        create_character_assets(
            self.character,
            [
                self._asset(1001, 19720),
                self._asset(1002, 19722),
                self._asset(1003, 19720),
            ],
        )

        assets = {
            a.item_id: a
            for a in EveCharacterAsset.objects.filter(character=self.character)
        }
        self.assertEqual(3, len(assets))
        self.assertEqual(19720, assets[1001].type_id)
        self.assertEqual("Revelation", assets[1001].type_name)
        self.assertEqual(19722, assets[1002].type_id)
        self.assertEqual("Naglfar", assets[1002].type_name)
        self.assertEqual(19720, assets[1003].type_id)
        self.assertEqual("Revelation", assets[1003].type_name)

    @patch("eveonline.helpers.characters.assets.EsiClient")
    def test_duplicate_cached_ship_type_creates_each_hull(self, esi_cls):
        esi = esi_cls.return_value
        esi.get_eve_type.return_value = _ship_type(19722, "Naglfar")
        eve_group = MagicMock()
        eve_group.eve_category.name = "Ship"
        esi.get_eve_group.return_value = eve_group

        create_character_assets(
            self.character,
            [
                self._asset(2001, 19722),
                self._asset(2002, 19722),
            ],
        )

        assets = list(
            EveCharacterAsset.objects.filter(
                character=self.character
            ).order_by("item_id")
        )
        self.assertEqual(2, len(assets))
        self.assertEqual(19722, assets[0].type_id)
        self.assertEqual(19722, assets[1].type_id)
        self.assertEqual("Naglfar", assets[0].type_name)
        self.assertEqual("Naglfar", assets[1].type_name)
