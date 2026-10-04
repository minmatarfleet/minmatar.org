"""Corporation and alliance autocomplete for structure scouting."""

from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import Client, TestCase

from campaigns.services.entities import search_entities
from campaigns.tests.helpers import auth_headers
from eveonline.client import EsiResponse, NO_VALID_ESI_TOKEN
from eveonline.models import EveAlliance, EveCorporation

BASE = "/api/campaigns/entities"


class EntitySearchApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create(username="scout")

    def test_anonymous_is_refused(self):
        response = self.client.get(BASE, {"kind": "corporation", "q": "host"})
        self.assertIn(response.status_code, (401, 403))

    def test_unknown_kind_is_rejected(self):
        response = self.client.get(
            BASE, {"kind": "faction", "q": "amarr"}, **auth_headers(self.user)
        )
        self.assertEqual(response.status_code, 400)

    def test_local_corporation_matches_name_and_ticker(self):
        EveCorporation.objects.create(
            corporation_id=99, name="Hostile Mining", ticker="HOST"
        )
        response = self.client.get(
            BASE,
            {"kind": "corporation", "q": "host"},
            **auth_headers(self.user)
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body[0]["id"], 99)
        self.assertEqual(body[0]["name"], "Hostile Mining")
        self.assertEqual(body[0]["kind"], "corporation")

    def test_short_query_returns_nothing(self):
        EveAlliance.objects.create(
            alliance_id=10, name="Curatores Veritatis Alliance", ticker="CVA"
        )
        response = self.client.get(
            BASE, {"kind": "alliance", "q": "c"}, **auth_headers(self.user)
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])


class EntitySearchEsiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="scout-esi")

    @patch(
        "campaigns.services.entities._search_character_ids",
        return_value=[3001],
    )
    @patch("campaigns.services.entities.EsiClient")
    def test_esi_ids_are_resolved_to_names(self, client_cls, characters):
        client = client_cls.return_value
        client.search_category.return_value = EsiResponse(
            200, {"alliance": [1988009451]}
        )
        client.resolve_universe_names.return_value = EsiResponse(
            0,
            [
                {
                    "id": 1988009451,
                    "name": "Curatores Veritatis Alliance",
                    "category": "alliance",
                }
            ],
        )

        matches = search_entities(self.user, "alliance", "Cura")
        self.assertEqual(matches[0]["id"], 1988009451)
        self.assertEqual(matches[0]["name"], "Curatores Veritatis Alliance")
        client.search_category.assert_called_once_with("alliance", "Cura")

    @patch(
        "campaigns.services.entities._search_character_ids",
        return_value=[3001, 3002],
    )
    @patch("campaigns.services.entities.EsiClient")
    def test_missing_scope_tries_the_next_character(
        self, client_cls, characters
    ):
        def factory(character_id):
            client = MagicMock()
            if character_id == 3001:
                client.search_category.return_value = EsiResponse(
                    NO_VALID_ESI_TOKEN
                )
            elif character_id == 3002:
                client.search_category.return_value = EsiResponse(
                    200, {"corporation": [42]}
                )
            else:
                client.resolve_universe_names.return_value = EsiResponse(
                    0,
                    [
                        {
                            "id": 42,
                            "name": "Sev3rance",
                            "category": "corporation",
                        }
                    ],
                )
            return client

        client_cls.side_effect = factory

        matches = search_entities(self.user, "corporation", "Sev")
        self.assertEqual([row["name"] for row in matches], ["Sev3rance"])
