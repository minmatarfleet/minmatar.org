import factory
from django.db.models import signals
from django.test import Client

from esi.models import Token

from app.test import TestCase
from eveonline.models import (
    EveCharacter,
    EveCorporation,
    EveAlliance,
)
from eveonline.helpers.characters import update_character_with_affiliations

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
        signals.post_save.disconnect(
            sender=EveAlliance,
            dispatch_uid="eve_alliance_post_save",
        )

        # create test client
        self.client = Client()

        super().setUp()

    def create_corp(self, corp_id: int, corp_name: str) -> EveCorporation:
        return EveCorporation.objects.create(
            corporation_id=corp_id,
            introduction="Intro",
            biography="Bio",
            timezones="TZ",
            requirements="Req",
            name=corp_name,
        )

    def test_get_corporations(self):
        self.create_corp(12345, "TestCorp")

        response = self.client.get(
            BASE_URL + "corporations",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        corps = response.json()
        self.assertEqual(1, len(corps))
        self.assertEqual("TestCorp", corps[0]["corporation_name"])

        self.create_corp(23456, "TestCorp 2")

        response = self.client.get(
            BASE_URL + "corporations",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        corps = response.json()
        self.assertEqual(2, len(corps))

    def test_get_corporation(self):
        self.create_corp(12345, "TestCorp")

        response = self.client.get(
            BASE_URL + "corporations/12345",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        corp = response.json()
        self.assertEqual(12345, corp["corporation_id"])
        self.assertEqual("TestCorp", corp["corporation_name"])

    def test_update_affiliations(self):
        EveCharacter.objects.create(
            character_id=100,
            character_name="Itsy Bitsy",
        )
        updated = update_character_with_affiliations(
            character_id=100, corporation_id=123, alliance_id=234
        )
        self.assertTrue(updated)
        character = EveCharacter.objects.get(character_id=100)
        self.assertEqual(character.corporation_id, 123)
        self.assertEqual(character.alliance_id, 234)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_get_corp_members(self):
        self.make_superuser()

        corp = self.create_corp(12345, "TestCorp")
        corp.ceo = EveCharacter.objects.create(
            character_id=10001,
            character_name="Boss Man",
            corporation_id=corp.corporation_id,
            user=self.user,
            token=Token.objects.create(
                character_id=10001,
                user=self.user,
            ),
        )
        corp.save()

        response = self.client.get(
            BASE_URL + "corporations/12345/members",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        members = response.json()
        self.assertEqual(1, len(members))
        self.assertEqual("Boss Man", members[0]["character_name"])
        self.assertEqual(1, members[0]["token_count"])
