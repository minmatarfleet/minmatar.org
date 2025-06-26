import factory
from typing import List
from unittest.mock import patch, MagicMock

from django.utils import timezone
from django.db.models import signals

from app.test import TestCase
from esi.models import Token, Scope

from eveonline.client import EsiResponse, EsiClient
from eveonline.scopes import CEO_SCOPES

from eveonline.tasks import (
    update_character_assets,
    update_character_skills,
    update_corporation,
    update_character_affilliations,
    update_character_killmails,
    setup_players,
    task_config,
)
from eveonline.models import (
    EveCharacter,
    EveCorporation,
    EveAlliance,
    EvePlayer,
    EveCharacterKillmail,
)


class EveOnlineTaskTests(TestCase):
    """
    Tests methods of the EveOnline tasks.
    """

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.helpers.assets.EsiClient")
    @patch("eveonline.tasks.EsiClient")
    def test_update_character_asset_task(self, task_mock, helper_mock):
        char = EveCharacter.objects.create(
            character_id=1,
            character_name="Test Char",
        )

        esi_mock = MagicMock(spec=EsiClient)
        task_mock.return_value = esi_mock
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

        (created, updated, deleted) = update_character_assets(char.id)

        self.assertEqual(1, created)
        self.assertEqual(0, updated)
        self.assertEqual(0, deleted)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_update_character_skills(self):
        char = EveCharacter.objects.create(
            character_id=1,
            character_name="Test Char",
        )

        with patch("eveonline.helpers.skills.EsiClient") as esi_mock:
            instance = esi_mock.return_value
            instance.get_character_skills.return_value = EsiResponse(
                response_code=200,
                data=[],
            )

            update_character_skills(char.id)

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
        self.add_token_scopes(token, CEO_SCOPES)
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

        with patch("eveonline.tasks.EsiClient") as esi_mock_1:
            with patch("eveonline.models.EsiClient") as esi_mock_2:
                esi_mock_1.return_value = mock_esi_client
                esi_mock_2.return_value = mock_esi_client

                update_corporation(corp.corporation_id)

                updated_corp = EveCorporation.objects.filter(
                    corporation_id=corp.corporation_id
                ).first()

                self.assertEqual("TICK", updated_corp.ticker)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_setup_players(self):
        EveCharacter.objects.create(
            character_id=1001,
            character_name="Testpilot1",
            user=self.user,
            is_primary=False,
        )
        EveCharacter.objects.create(
            character_id=1002,
            character_name="Testpilot2",
            user=self.user,
            is_primary=True,
        )

        self.assertEqual(0, EvePlayer.objects.count())

        setup_players()

        self.assertEqual(1, EvePlayer.objects.count())

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.tasks.EsiClient")
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
            EveCharacter.objects.get(character_id=10001).corporation
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
    @patch("eveonline.tasks.EsiClient")
    def test_update_character_killmails(self, esi_mock):
        esi = esi_mock.return_value

        char = EveCharacter.objects.create(
            character_id=1001,
            character_name="Test Pilot",
            user=self.user,
            is_primary=False,
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

        self.assertEqual(0, EveCharacterKillmail.objects.count())

        update_character_killmails(char.character_id)

        self.assertEqual(1, EveCharacterKillmail.objects.count())
