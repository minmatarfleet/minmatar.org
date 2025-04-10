from django.db.models import signals
from django.test import Client
from django.contrib.auth.models import User

from esi.models import Token
from app.test import TestCase
from eveonline.models import (
    EveCharacter,
    EveCorporation,
)

BASE_URL = "/api/eveonline/corporations/"


class CorporationRouterTestCase(TestCase):
    """Test cases for the corporation router."""

    def setUp(self):
        # disconnect signals
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_public_data",
        )
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_private_data",
        )

        # create test client
        self.client = Client()

        super().setUp()

    def create_corp(self, corp_id: int, corp_name: str) -> EveCorporation:
        return EveCorporation.objects.create(
            corporation_id=corp_id,
            introduction = "Intro",
            biography = "Bio",
            timezones = "TZ",
            requirements = "Req",
            name = corp_name,
        )

    def test_get_corporations(self):
        self.create_corp(12345, "TestCorp")
        
        response = self.client.get(
            BASE_URL+"corporations", HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )

        self.assertEqual(200, response.status_code)
        corps = response.json()
        self.assertEqual(1, len(corps))
        self.assertEqual("TestCorp", corps[0]["corporation_name"])

        self.create_corp(23456, "TestCorp 2")

        response = self.client.get(
            BASE_URL+"corporations", HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )

        self.assertEqual(200, response.status_code)
        corps = response.json()
        self.assertEqual(2, len(corps))

    def test_get_corporation(self):
        self.create_corp(12345, "TestCorp")

        response = self.client.get(
            BASE_URL+"corporations/12345", HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )

        self.assertEqual(200, response.status_code)
        corp = response.json()
        self.assertEqual(12345, corp["corporation_id"])
        self.assertEqual("TestCorp", corp["corporation_name"])
