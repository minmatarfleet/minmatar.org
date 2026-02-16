import factory
from typing import List
from unittest.mock import patch, MagicMock

from django.utils import timezone
from django.db.models import signals

from app.test import TestCase
from esi.models import Token, Scope

from eveonline.client import EsiResponse, EsiClient
from eveonline.scopes import scopes_for, TokenType

from eveonline.helpers.characters import (
    update_character_assets as helper_update_character_assets,
)
from eveonline.tasks import (
    update_character,
    update_corporation,
    update_character_affilliations,
    setup_players,
    task_config,
)
from eveonline.models import (
    EveCharacter,
    EveCorporation,
    EveAlliance,
    EvePlayer,
    EveCharacterKillmail,
    EveLocation,
    EveCharacterAsset,
)


class EveOnlineTaskTests(TestCase):
    """
    Tests methods of the EveOnline tasks.
    """

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.helpers.characters.assets.EsiClient")
    @patch("eveonline.helpers.characters.update.EsiClient")
    def test_update_character_asset_task(self, update_mock, helper_mock):
        char = EveCharacter.objects.create(
            character_id=1,
            character_name="Test Char",
        )

        esi_mock = MagicMock(spec=EsiClient)
        update_mock.return_value = esi_mock
        helper_mock.return_value = esi_mock

        esi_mock.get_character_assets.return_value = EsiResponse(
            response_code=200,
            data=[
                {
                    "is_singleton": True,
                    "item_id": 1041120583167,
                    "location_flag": "Hangar",
                    "location_id": 60004600,
                    "location_type": "station",
                    "quantity": 1,
                    "type_id": 73794,
                }
            ],
        )
        esi_mock.get_eve_type.return_value.eve_group.id = 123
        esi_mock.get_eve_type.return_value.id = 100
        esi_mock.get_eve_type.return_value.name = "Thrasher"
        esi_mock.get_eve_group.return_value.eve_category.name = "Ship"
        esi_mock.get_station.return_value.name = "Home Base"

        created, updated, deleted = helper_update_character_assets(char.id)

        self.assertEqual(1, created)
        self.assertEqual(0, updated)
        self.assertEqual(0, deleted)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.helpers.characters.assets.EsiClient")
    @patch("eveonline.helpers.characters.update.EsiClient")
    def test_update_character_asset_task_with_evelocation(
        self, update_mock, helper_mock
    ):
        char = EveCharacter.objects.create(
            character_id=1,
            character_name="Test Char",
        )

        # Create an EveLocation for testing
        EveLocation.objects.create(
            location_id=123456789,
            location_name="Test Structure",
            solar_system_id=30000142,
            solar_system_name="Jita",
            short_name="TEST",
        )

        esi_mock = MagicMock(spec=EsiClient)
        update_mock.return_value = esi_mock
        helper_mock.return_value = esi_mock

        esi_mock.get_character_assets.return_value = EsiResponse(
            response_code=200,
            data=[
                {
                    "is_singleton": True,
                    "item_id": 1041120583168,
                    "location_flag": "Hangar",
                    "location_id": 123456789,
                    "location_type": "item",
                    "quantity": 1,
                    "type_id": 73794,
                }
            ],
        )
        esi_mock.get_eve_type.return_value.eve_group.id = 123
        esi_mock.get_eve_type.return_value.id = 100
        esi_mock.get_eve_type.return_value.name = "Thrasher"
        esi_mock.get_eve_group.return_value.eve_category.name = "Ship"

        created, updated, deleted = helper_update_character_assets(char.id)

        self.assertEqual(1, created)
        self.assertEqual(0, updated)
        self.assertEqual(0, deleted)

        # Verify the asset was created with the correct location name
        asset = EveCharacterAsset.objects.get(character=char)
        self.assertEqual(asset.location_name, "Test Structure")
        self.assertEqual(asset.location_id, 123456789)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.helpers.characters.assets.EsiClient")
    @patch("eveonline.helpers.characters.update.EsiClient")
    def test_update_character_asset_task_with_missing_evelocation(
        self, update_mock, helper_mock
    ):
        char = EveCharacter.objects.create(
            character_id=1,
            character_name="Test Char",
        )

        esi_mock = MagicMock(spec=EsiClient)
        update_mock.return_value = esi_mock
        helper_mock.return_value = esi_mock

        esi_mock.get_character_assets.return_value = EsiResponse(
            response_code=200,
            data=[
                {
                    "is_singleton": True,
                    "item_id": 1041120583169,
                    "location_flag": "Hangar",
                    "location_id": 999999999,
                    "location_type": "item",
                    "quantity": 1,
                    "type_id": 73794,
                }
            ],
        )
        esi_mock.get_eve_type.return_value.eve_group.id = 123
        esi_mock.get_eve_type.return_value.id = 100
        esi_mock.get_eve_type.return_value.name = "Thrasher"
        esi_mock.get_eve_group.return_value.eve_category.name = "Ship"

        created, updated, deleted = helper_update_character_assets(char.id)

        self.assertEqual(1, created)
        self.assertEqual(0, updated)
        self.assertEqual(0, deleted)

        # Verify the asset was created with the unknown location name
        asset = EveCharacterAsset.objects.get(character=char)
        self.assertEqual(asset.location_name, "Unknown Location - 999999999")
        self.assertEqual(asset.location_id, 999999999)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.helpers.characters.update.EsiClient")
    def test_update_character_skills(self, update_esi_mock):
        char = EveCharacter.objects.create(
            character_id=1,
            character_name="Test Char",
        )
        update_esi_mock.return_value.get_character_assets.return_value = (
            EsiResponse(response_code=200, data=[])
        )
        update_esi_mock.return_value.get_recent_killmails.return_value = (
            EsiResponse(response_code=200, data=[])
        )

        with patch(
            "eveonline.helpers.characters.skills.EsiClient"
        ) as skills_mock:
            skills_mock.return_value.get_character_skills.return_value = (
                EsiResponse(response_code=200, data=[])
            )
            update_character(char.id)

    def add_token_scopes(self, token: Token, scopes: List[str]):
        for required_scope in scopes:
            scope, _ = Scope.objects.get_or_create(name=required_scope)
            token.scopes.add(scope)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_update_corporation(self):
        alliance = EveAlliance.objects.create(
            alliance_id=99011978,
        )
        corp = EveCorporation.objects.create(
            corporation_id=123,
            alliance=alliance,
        )
        token = Token.objects.create(character_id=90000001)
        self.add_token_scopes(token, scopes_for(TokenType.DIRECTOR))
        EveCharacter.objects.create(
            character_id=token.character_id,
            token=token,
        )
        self.assertEqual("alliance", corp.type)

        mock_esi_client = MagicMock(EsiClient)

        mock_esi_client.get_corporation.return_value = EsiResponse(
            response_code=200,
            data={
                "name": "TestCorp",
                "ticker": "TICK",
                "member_count": 1,
                "alliance_id": 99011978,
                "ceo_id": 90000001,
            },
        )

        mock_esi_client.get_corporation_members.return_value = EsiResponse(
            response_code=200,
            data=[1],
        )

        mock_esi_client.get_corporation_roles.return_value = EsiResponse(
            response_code=200,
            data=[],
        )

        with patch(
            "eveonline.models.corporations.EsiClient"
        ) as esi_mock_model:
            with patch(
                "eveonline.helpers.corporations.update.EsiClient"
            ) as esi_mock_helper:
                esi_mock_model.return_value = mock_esi_client
                esi_mock_helper.return_value = mock_esi_client

                update_corporation(corp.corporation_id)

                updated_corp = EveCorporation.objects.filter(
                    corporation_id=corp.corporation_id
                ).first()

                self.assertEqual("TICK", updated_corp.ticker)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_setup_players(self):
        primary_char = EveCharacter.objects.create(
            character_id=1002,
            character_name="Testpilot2",
            user=self.user,
        )
        # Set up the primary character via EvePlayer (simulating existing data)
        EvePlayer.objects.create(
            user=self.user,
            primary_character=primary_char,
            nickname=self.user.username,
        )

        self.assertEqual(1, EvePlayer.objects.count())

        # setup_players should ensure EvePlayer exists for users with primary characters
        setup_players()

        # Should still be 1 (get_or_create won't create duplicate)
        self.assertEqual(1, EvePlayer.objects.count())
        player = EvePlayer.objects.get(user=self.user)
        self.assertEqual(player.primary_character, primary_char)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.tasks.affiliations.EsiClient")
    def test_update_character_affilliations(self, esi_mock):
        esi_client = esi_mock.return_value

        task_config["async_apply_affiliations"] = False

        EveCorporation.objects.create(
            corporation_id=20001,
        )

        EveCharacter.objects.create(
            character_id=10001,
            character_name="Char1",
            user=self.user,
        )

        self.assertIsNone(
            EveCharacter.objects.get(character_id=10001).corporation_id
        )

        esi_client.get_character_affiliations.return_value = EsiResponse(
            response_code=200,
            data=[
                {
                    "character_id": 10001,
                    "corporation_id": 20001,
                    "alliance_id": None,
                    "faction_id": None,
                }
            ],
        )

        updated = update_character_affilliations()

        self.assertEqual(1, updated)

        self.assertIsNotNone(
            EveCharacter.objects.get(character_id=10001).corporation_id
        )

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.helpers.characters.skills.EsiClient")
    @patch("eveonline.helpers.characters.update.EsiClient")
    def test_update_character_killmails(
        self, update_esi_mock, skills_esi_mock
    ):
        esi = update_esi_mock.return_value
        esi.get_character_assets.return_value = EsiResponse(
            response_code=200, data=[]
        )
        esi.get_recent_killmails.return_value = EsiResponse(
            response_code=200,
            data=[
                {
                    "killmail_id": 12345678,
                    "killmail_hash": "abc123xyz",
                }
            ],
        )
        esi.get_character_killmail.return_value = EsiResponse(
            response_code=200,
            data={
                "solar_system_id": 100001,
                "killmail_time": timezone.now(),
                "victim": {"ship_type_id": 50001, "items": "list of items"},
                "attackers": "list of attackers",
            },
        )
        skills_esi_mock.return_value.get_character_skills.return_value = (
            EsiResponse(response_code=200, data=[])
        )

        char = EveCharacter.objects.create(
            character_id=1001,
            character_name="Test Pilot",
            user=self.user,
        )
        token = Token.objects.create(character_id=char.character_id)
        self.add_token_scopes(token, ["esi-killmails.read_killmails.v1"])

        self.assertEqual(0, EveCharacterKillmail.objects.count())

        update_character(char.character_id)

        self.assertEqual(1, EveCharacterKillmail.objects.count())
