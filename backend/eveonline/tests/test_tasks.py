from typing import List
from unittest.mock import patch, MagicMock

from app.test import TestCase
from esi.models import Token, Scope
from eveonline.client import EsiResponse, EsiClient
from eveonline.scopes import CEO_SCOPES

from eveonline.tasks import (
    update_character_assets,
    update_character_skills,
    update_corporation,
)
from eveonline.models import EveCharacter, EveCorporation, EveAlliance


class EveOnlineTaskTests(TestCase):
    """
    Tests methods of the EveOnline tasks.
    """

    def test_update_character_asset_task(self):
        char = EveCharacter.objects.create(
            character_id=1,
            character_name="Test Char",
        )

        with patch("eveonline.tasks.EsiClient") as esi_mock:
            instance = esi_mock.return_value
            instance.get_character_assets.return_value = EsiResponse(
                response_code=200, data=[]
            )

            #  No data returned by ESI, so won't actually test creating assets

            update_character_assets(char.id)

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
