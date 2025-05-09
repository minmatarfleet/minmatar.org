from django.test import Client

from app.test import TestCase

from eveonline.models import EveCharacter
from eveonline.helpers.characters import set_primary_character
from fleets.tests import (
    disconnect_fleet_signals,
    setup_fleet_reference_data,
    make_test_fleet,
)

BASE_URL = "/api/srp"
KM_LINK = "https://esi.evetech.net/latest/killmails/126008813/9c92aa157f138da9b5a64abbd8225893f1b8b5f0/"


class SrpRouterTestCase(TestCase):
    """Test cases for the market router."""

    def setUp(self):
        # create test client
        self.client = Client()

        super().setUp()

        # Setup fleet stuff
        disconnect_fleet_signals()
        setup_fleet_reference_data()
        self.fleet = make_test_fleet("Test fleet", self.user)

    def test_basic_srp(self):
        fc_char = EveCharacter.objects.create(
            character_id=634915984,
            character_name="Mr FC",
            user=self.user,
        )
        set_primary_character(self.user, fc_char)

        data = {
            "external_killmail_link": KM_LINK,
            "fleet_id": self.fleet.id,
            "is_corp_ship": False,
        }
        response = self.client.post(
            f"{BASE_URL}",
            data,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
