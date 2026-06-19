"""Tests for character asset sync helpers."""

from unittest.mock import MagicMock, patch

from app.test import TestCase
from eveonline.helpers.characters.assets import create_character_assets
from eveonline.models import EveCharacter, EveCharacterAsset, EveLocation
from eveuniverse.models import EveCategory, EveGroup, EveType


def _ship_type(type_id: int, name: str):
    eve_type = MagicMock()
    eve_type.id = type_id
    eve_type.name = name
    eve_group = MagicMock()
    eve_group.id = 1
    eve_group.eve_category.name = "Ship"
    eve_type.eve_group = eve_group
    return eve_type


class CreateCharacterAssetsTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.category, _ = EveCategory.objects.get_or_create(
            id=9001,
            defaults={"name": "Ship", "published": True},
        )
        cls.group, _ = EveGroup.objects.get_or_create(
            id=9001,
            defaults={
                "name": "Frigate",
                "published": True,
                "eve_category": cls.category,
            },
        )
        cls.ship_type, _ = EveType.objects.get_or_create(
            id=9001,
            defaults={
                "name": "Test Frigate",
                "published": True,
                "eve_group": cls.group,
            },
        )

    @patch("eveonline.helpers.characters.assets.EsiClient")
    def test_create_character_assets_bulk_create_ships_only(
        self, esi_client_cls
    ):
        character = EveCharacter.objects.create(
            character_id=5001,
            character_name="Asset Pilot",
        )
        EveLocation.objects.create(
            location_id=6001,
            location_name="Ship Hangar",
            solar_system_id=1,
            solar_system_name="Test",
        )
        station_mock = MagicMock()
        station_mock.name = "Test Station"
        esi_client_cls.return_value.get_station.return_value = station_mock

        assets_data = [
            {
                "is_blueprint_copy": False,
                "is_singleton": False,
                "item_id": 7001,
                "location_flag": "Hangar",
                "location_id": 8001,
                "location_type": "station",
                "quantity": 1,
                "type_id": self.ship_type.id,
            },
            {
                "is_blueprint_copy": False,
                "is_singleton": False,
                "item_id": 7002,
                "location_flag": "DroneBay",
                "location_id": 6001,
                "location_type": "item",
                "quantity": 5,
                "type_id": self.ship_type.id,
            },
        ]

        created, updated, deleted = create_character_assets(
            character, assets_data
        )

        self.assertEqual(1, created)
        self.assertEqual(0, updated)
        self.assertEqual(0, deleted)
        saved = EveCharacterAsset.objects.get(character=character)
        self.assertEqual("Test Frigate", saved.type_name)
        self.assertEqual(7001, saved.item_id)

    @patch("eveonline.helpers.characters.assets.EsiClient")
    def test_cached_ship_after_different_ship_uses_correct_type_id(
        self, esi_cls
    ):
        """A cache hit after syncing another hull must not reuse the prior eve_type.id."""
        character = EveCharacter.objects.create(
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
        esi = esi_cls.return_value
        esi.get_eve_type.side_effect = [
            _ship_type(19720, "Revelation"),
            _ship_type(19722, "Naglfar"),
        ]

        create_character_assets(
            character,
            [
                {
                    "is_singleton": True,
                    "item_id": 1001,
                    "location_flag": "Hangar",
                    "location_id": 1053229023468,
                    "location_type": "item",
                    "quantity": 1,
                    "type_id": 19720,
                },
                {
                    "is_singleton": True,
                    "item_id": 1002,
                    "location_flag": "Hangar",
                    "location_id": 1053229023468,
                    "location_type": "item",
                    "quantity": 1,
                    "type_id": 19722,
                },
                {
                    "is_singleton": True,
                    "item_id": 1003,
                    "location_flag": "Hangar",
                    "location_id": 1053229023468,
                    "location_type": "item",
                    "quantity": 1,
                    "type_id": 19720,
                },
            ],
        )

        assets = {
            asset.item_id: asset
            for asset in EveCharacterAsset.objects.filter(character=character)
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
        character = EveCharacter.objects.create(
            character_id=99002,
            character_name="Test Pilot 2",
        )
        EveLocation.objects.create(
            location_id=1053229023469,
            location_name="R-6KYM - Casper Anchored It 2",
            solar_system_id=30002324,
            solar_system_name="R-6KYM",
            short_name="R-6KYM",
        )
        esi = esi_cls.return_value
        esi.get_eve_type.return_value = _ship_type(19722, "Naglfar")

        create_character_assets(
            character,
            [
                {
                    "is_singleton": True,
                    "item_id": 2001,
                    "location_flag": "Hangar",
                    "location_id": 1053229023469,
                    "location_type": "item",
                    "quantity": 1,
                    "type_id": 19722,
                },
                {
                    "is_singleton": True,
                    "item_id": 2002,
                    "location_flag": "Hangar",
                    "location_id": 1053229023469,
                    "location_type": "item",
                    "quantity": 1,
                    "type_id": 19722,
                },
            ],
        )

        assets = list(
            EveCharacterAsset.objects.filter(character=character).order_by(
                "item_id"
            )
        )
        self.assertEqual(2, len(assets))
        self.assertEqual(19722, assets[0].type_id)
        self.assertEqual(19722, assets[1].type_id)
        self.assertEqual("Naglfar", assets[0].type_name)
        self.assertEqual("Naglfar", assets[1].type_name)
