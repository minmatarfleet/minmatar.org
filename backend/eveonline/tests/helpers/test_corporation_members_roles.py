"""Tests for corporation members/roles sync, including title-granted roles."""

from unittest.mock import patch

import factory
from django.db.models import signals
from esi.models import Scope, Token

from app.test import TestCase
from eveonline.client import EsiResponse
from eveonline.helpers.corporations.update import (
    title_granted_roles_by_character,
    update_corporation_members_and_roles,
)
from eveonline.models import EveAlliance, EveCharacter, EveCorporation
from eveonline.scopes import scopes_for, TokenType


def _director_token(character_id: int) -> Token:
    token = Token.objects.create(character_id=character_id)
    for scope_name in scopes_for(TokenType.DIRECTOR):
        scope, _ = Scope.objects.get_or_create(name=scope_name)
        token.scopes.add(scope)
    return token


class TitleGrantedRolesByCharacterTestCase(TestCase):
    def test_maps_title_roles_onto_members(self):
        titles = [
            {
                "title_id": 2048,
                "name": "Recruiter",
                "roles": ["Personnel_Manager"],
                "roles_at_hq": [],
                "roles_at_base": [],
                "roles_at_other": [],
            },
            {
                "title_id": 1,
                "name": "XO",
                "roles": ["Personnel_Manager", "Station_Manager"],
                "roles_at_hq": ["Hangar_Take_1"],
                "roles_at_base": [],
                "roles_at_other": [],
            },
        ]
        member_titles = [
            {"character_id": 2124486772, "titles": [2048]},
            {"character_id": 111, "titles": [1, 2048]},
            {"character_id": 222, "titles": []},
        ]

        granted = title_granted_roles_by_character(titles, member_titles)

        self.assertEqual(
            {"Personnel_Manager"},
            granted[2124486772],
        )
        self.assertEqual(
            {"Personnel_Manager", "Station_Manager", "Hangar_Take_1"},
            granted[111],
        )
        self.assertNotIn(222, granted)


class UpdateCorporationMembersAndRolesTestCase(TestCase):
    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def setUp(self):
        alliance = EveAlliance.objects.create(alliance_id=99011978)
        self.corporation = EveCorporation.objects.create(
            corporation_id=98741376,
            name="Minmatar Fleet Academy",
            ticker="L3ARN",
            alliance=alliance,
            recruitment_active=True,
        )
        token = _director_token(2123699290)
        self.ceo = EveCharacter.objects.create(
            character_id=token.character_id,
            character_name="Lilith Himmelsgaenger",
            token=token,
            corporation_id=self.corporation.corporation_id,
        )
        self.corporation.ceo = self.ceo
        self.corporation.save()

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.helpers.corporations.update.EsiClient")
    def test_title_personnel_manager_makes_recruiter(self, esi_client_cls):
        """Roles endpoint empty but Recruiter title grants Personnel_Manager."""
        esi = esi_client_cls.return_value
        esi.get_corporation_members.return_value = EsiResponse(
            response_code=200,
            data=[2124486772, 2116866003],
        )
        esi.get_corporation_roles.return_value = EsiResponse(
            response_code=200,
            data=[
                {
                    "character_id": 2124486772,
                    "roles": [],
                    "roles_at_hq": [],
                    "roles_at_base": [],
                    "roles_at_other": [],
                },
                {
                    "character_id": 2116866003,
                    "roles": ["Personnel_Manager"],
                    "roles_at_hq": [],
                    "roles_at_base": [],
                    "roles_at_other": [],
                },
            ],
        )
        esi.get_corporation_titles.return_value = EsiResponse(
            response_code=200,
            data=[
                {
                    "title_id": 2048,
                    "name": "Recruiter",
                    "roles": ["Personnel_Manager"],
                    "roles_at_hq": [],
                    "roles_at_base": [],
                    "roles_at_other": [],
                }
            ],
        )
        esi.get_corporation_member_titles.return_value = EsiResponse(
            response_code=200,
            data=[
                {"character_id": 2124486772, "titles": [2048]},
                {"character_id": 2116866003, "titles": [2048]},
            ],
        )

        update_corporation_members_and_roles(self.corporation.corporation_id)

        recruiters = set(
            self.corporation.recruiters.values_list("character_id", flat=True)
        )
        self.assertEqual({2124486772, 2116866003}, recruiters)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.helpers.corporations.update.EsiClient")
    def test_title_station_manager_makes_steward(self, esi_client_cls):
        esi = esi_client_cls.return_value
        esi.get_corporation_members.return_value = EsiResponse(
            response_code=200,
            data=[1001],
        )
        esi.get_corporation_roles.return_value = EsiResponse(
            response_code=200,
            data=[
                {
                    "character_id": 1001,
                    "roles": [],
                    "roles_at_hq": [],
                    "roles_at_base": [],
                    "roles_at_other": [],
                }
            ],
        )
        esi.get_corporation_titles.return_value = EsiResponse(
            response_code=200,
            data=[
                {
                    "title_id": 9,
                    "name": "Gunner",
                    "roles": ["Station_Manager"],
                    "roles_at_hq": [],
                    "roles_at_base": [],
                    "roles_at_other": [],
                }
            ],
        )
        esi.get_corporation_member_titles.return_value = EsiResponse(
            response_code=200,
            data=[{"character_id": 1001, "titles": [9]}],
        )

        update_corporation_members_and_roles(self.corporation.corporation_id)

        self.assertEqual(
            [1001],
            list(
                self.corporation.stewards.values_list(
                    "character_id", flat=True
                )
            ),
        )

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.helpers.corporations.update.EsiClient")
    def test_continues_without_titles_when_titles_esi_fails(
        self, esi_client_cls
    ):
        esi = esi_client_cls.return_value
        esi.get_corporation_members.return_value = EsiResponse(
            response_code=200,
            data=[2116866003],
        )
        esi.get_corporation_roles.return_value = EsiResponse(
            response_code=200,
            data=[
                {
                    "character_id": 2116866003,
                    "roles": ["Personnel_Manager"],
                    "roles_at_hq": [],
                    "roles_at_base": [],
                    "roles_at_other": [],
                }
            ],
        )
        esi.get_corporation_titles.return_value = EsiResponse(
            response_code=403
        )
        esi.get_corporation_member_titles.return_value = EsiResponse(
            response_code=200,
            data=[],
        )

        update_corporation_members_and_roles(self.corporation.corporation_id)

        self.assertEqual(
            [2116866003],
            list(
                self.corporation.recruiters.values_list(
                    "character_id", flat=True
                )
            ),
        )
