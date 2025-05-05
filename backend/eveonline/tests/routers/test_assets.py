from django.db.models import signals
from django.test import Client

from app.test import TestCase
from eveonline.models import (
    EveCharacterAsset,
    EveCharacter,
    EveCorporation,
    EveAlliance,
)

BASE_URL = "/api/eveonline/assets"


class AssetRouterTestCase(TestCase):
    """Test cases for the character asset router."""

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

    def make_superuser(self):
        self.user.is_superuser = True
        self.user.save()

    def setup_alliance(self):
        alliance = EveAlliance.objects.create(
            alliance_id=1,
            name="FL33T",
            ticker="FL33T",
        )
        corp = EveCorporation.objects.create(
            alliance=alliance,
            corporation_id=1,
        )
        char1 = EveCharacter.objects.create(
            character_id=1,
            character_name="Player 1",
            corporation=corp,
        )
        char2 = EveCharacter.objects.create(
            character_id=2,
            character_name="Player 2",
            corporation=corp,
        )
        return alliance, corp, char1, char2

    def create_asset(
        self, char, type_id, type_name, location_id, location_name
    ):
        return EveCharacterAsset.objects.create(
            type_id=type_id,
            type_name=type_name,
            location_id=location_id,
            location_name=location_name,
            character=char,
        )

    def test_get_asset_summary(self):
        _, _, char1, char2 = self.setup_alliance()

        self.create_asset(char1, 72811, "Cyclone Fleet Issue", 1, "Jita Fort")
        self.create_asset(char2, 72811, "Cyclone Fleet Issue", 1, "Jita Fort")
        self.create_asset(char1, 11957, "Falcon", 1, "Jita Fort")
        self.create_asset(char1, 72811, "Cyclone Fleet Issue", 2, "Amarr Fort")
        self.create_asset(char1, 17732, "Tempest Fleet Issue", 1, "Jita Fort")

        response = self.client.get(
            f"{BASE_URL}/ships", HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    "location_name": "Jita Fort",
                    "type_name": "Cyclone Fleet Issue",
                    "total": 2,
                },
                {
                    "location_name": "Amarr Fort",
                    "type_name": "Cyclone Fleet Issue",
                    "total": 1,
                },
                {
                    "location_name": "Jita Fort",
                    "type_name": "Tempest Fleet Issue",
                    "total": 1,
                },
            ],
        )
