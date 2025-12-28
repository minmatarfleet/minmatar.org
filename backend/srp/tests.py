from django.test import Client
from unittest.mock import patch, ANY

from eveuniverse.models import EveType, EveGroup

from app.test import TestCase

from eveonline.client import EsiResponse
from eveonline.models import EveCharacter
from eveonline.helpers.characters import set_primary_character
from combatlog.models import CombatLog
from fleets.tests import (
    disconnect_fleet_signals,
    setup_fleet_reference_data,
    make_test_fleet,
)
from srp.models import EveFleetShipReimbursement, ShipReimbursementAmount
from srp.helpers import get_reimbursement_amount

BASE_URL = "/api/srp"

KM_CHAR = 634915984
KM_ID = 126008813
KM_HASH = "9c92aa157f138da9b5a64abbd8225893f1b8b5f0"
KM_LINK = f"https://esi.evetech.net/latest/killmails/{KM_ID}/{KM_HASH}/"


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

    @patch("srp.helpers.EsiClient")
    def test_basic_srp(self, esi_mock):
        esi = esi_mock.return_value

        fc_char = EveCharacter.objects.create(
            character_id=KM_CHAR,
            character_name="Mr FC",
            user=self.user,
        )
        set_primary_character(self.user, fc_char)

        esi.get_character_killmail.return_value = EsiResponse(
            response_code=200,
            data={
                "victim": {
                    "character_id": fc_char.character_id,
                    "ship_type_id": 11400,
                },
                "killmail_time": "2025-04-02T11:47:15Z",
            },
        )
        esi.get_eve_type.return_value = EveType(
            id=11400,
            description="Jaguar",
            eve_group=EveGroup(),
        )

        data = {
            "external_killmail_link": KM_LINK,
            "fleet_id": self.fleet.id,
            "is_corp_ship": False,
            "category": "dps",
            "comments": "Testing FTW",
        }
        response = self.client.post(
            f"{BASE_URL}",
            data,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual("dps", data["category"])
        self.assertEqual("Testing FTW", data["comments"])

    @patch("srp.helpers.EsiClient")
    def test_non_fleet_srp(self, esi_mock):
        esi = esi_mock.return_value

        self.make_superuser()

        fc_char = EveCharacter.objects.create(
            character_id=KM_CHAR,
            character_name="Mr FC",
            user=self.user,
        )
        set_primary_character(self.user, fc_char)

        esi.get_character_killmail.return_value = EsiResponse(
            response_code=200,
            data={
                "victim": {
                    "character_id": fc_char.character_id,
                    "ship_type_id": 11400,
                },
                "killmail_time": "2025-04-02T11:47:15Z",
            },
        )
        esi.get_eve_type.return_value = EveType(
            id=11400,
            description="Jaguar",
            eve_group=EveGroup(),
        )

        # Create non-fleet SRP request
        data = {
            "external_killmail_link": KM_LINK,
            "is_corp_ship": False,
        }
        response = self.client.post(
            f"{BASE_URL}",
            data,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        reimbursement = response.json()
        reimbursement_id = reimbursement["id"]
        self.assertIsNotNone(reimbursement_id)
        self.assertIsNone(reimbursement["fleet_id"])
        self.assertEqual("pending", reimbursement["status"])

        # Get all SRP requests
        response = self.client.get(
            f"{BASE_URL}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        reimbursements = response.json()
        self.assertEqual(1, len(reimbursements))
        self.assertEqual(reimbursement_id, reimbursements[0]["id"])

        # Approve SRP request with mocked ESI client
        esi.send_evemail.return_value = EsiResponse(
            response_code=200, data="Success"
        )

        data = {"status": "approved"}
        response = self.client.patch(
            f"{BASE_URL}/{reimbursement_id}",
            data,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        patch_status = response.json()
        self.assertEqual("Success", patch_status["database_update_status"])
        self.assertEqual("Success", patch_status["evemail_status"])

        esi.send_evemail.assert_called_once_with(
            {
                "subject": "SRP Reimbursement Decision",
                "body": ANY,
                "recipients": [
                    {
                        "recipient_id": KM_CHAR,
                        "recipient_type": "character",
                    }
                ],
            }
        )

    def test_user_srp(self):
        self.make_superuser()
        fc_char = EveCharacter.objects.create(
            character_id=634915984,
            character_name="Mr FC",
            user=self.user,
        )
        set_primary_character(self.user, fc_char)

        EveFleetShipReimbursement.objects.create(
            user=self.user,
            status="pending",
            killmail_id=1234,
            external_killmail_link="abc",
            character_id=fc_char.character_id,
            character_name=fc_char.character_name,
            primary_character_id=fc_char.character_id,
            primary_character_name=fc_char.character_name,
            amount=1.23,
            ship_name="Rifter",
            ship_type_id=1234567,
        )
        EveFleetShipReimbursement.objects.create(
            status="pending",
            killmail_id=2345,
            external_killmail_link="xyz",
            character_id=fc_char.character_id,
            character_name=fc_char.character_name,
            primary_character_id=fc_char.character_id,
            primary_character_name=fc_char.character_name,
            amount=1.23,
            ship_name="Rifter",
            ship_type_id=1234567,
        )

        response = self.client.get(
            f"{BASE_URL}?user_id={self.user.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        reimbursements = response.json()
        self.assertEqual(1, len(reimbursements))
        self.assertEqual("abc", reimbursements[0]["external_killmail_link"])

    def test_withdraw_srp(self):
        fc_char = EveCharacter.objects.create(
            character_id=634915984,
            character_name="Mr FC",
            user=self.user,
        )
        set_primary_character(self.user, fc_char)

        srp = EveFleetShipReimbursement.objects.create(
            user=self.user,
            status="pending",
            killmail_id=1234,
            external_killmail_link="abc",
            character_id=fc_char.character_id,
            character_name=fc_char.character_name,
            primary_character_id=fc_char.character_id,
            primary_character_name=fc_char.character_name,
            amount=1.23,
            ship_name="Rifter",
            ship_type_id=1234567,
        )

        data = {"status": "withdrawn"}
        response = self.client.patch(
            f"{BASE_URL}/{srp.id}",
            data=data,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        result = response.json()
        self.assertEqual("N/A", result["evemail_status"])

        data = {"status": "approved"}
        response = self.client.patch(
            f"{BASE_URL}/{srp.id}",
            data=data,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(403, response.status_code)

    def test_srp_values_from_database(self):
        ShipReimbursementAmount.objects.create(
            kind="type",
            name="Thrasher",
            srp_value=12000000,
        )
        ShipReimbursementAmount.objects.create(
            kind="class",
            name="Cruiser",
            srp_value=20000000,
        )

        thrasher = EveType(
            name="Thrasher",
            eve_group=EveGroup(
                name="Destroyer",
            ),
        )
        self.assertEqual(12000000, get_reimbursement_amount(thrasher))

        stabber = EveType(
            name="Stabber",
            eve_group=EveGroup(
                name="Cruiser",
            ),
        )
        self.assertEqual(20000000, get_reimbursement_amount(stabber))

    def test_invalid_killmail_link(self):
        data = {
            "external_killmail_link": "This won't work",
            "is_corp_ship": False,
            "category": "dps",
            "comments": "Testing FTW",
        }
        response = self.client.post(
            f"{BASE_URL}",
            data,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(400, response.status_code)
        self.assertEqual("Killmail link not valid", response.json()["detail"])

    @patch("srp.helpers.EsiClient")
    def test_srp_with_log(self, esi_mock):
        self.make_superuser()
        esi = esi_mock.return_value

        fc_char = EveCharacter.objects.create(
            character_id=KM_CHAR,
            character_name="Mr FC",
            user=self.user,
        )
        set_primary_character(self.user, fc_char)

        esi.get_character_killmail.return_value = EsiResponse(
            response_code=200,
            data={
                "victim": {
                    "character_id": fc_char.character_id,
                    "ship_type_id": 11400,
                },
                "killmail_time": "2025-04-02T11:47:15Z",
            },
        )
        esi.get_eve_type.return_value = EveType(
            id=11400,
            description="Jaguar",
            eve_group=EveGroup(),
        )

        combat_log = CombatLog.objects.create()

        data = {
            "external_killmail_link": KM_LINK,
            "fleet_id": self.fleet.id,
            "is_corp_ship": False,
            "category": "dps",
            "comments": "Testing FTW",
            "combat_log_id": combat_log.id,
        }
        response = self.client.post(
            f"{BASE_URL}",
            data,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual("dps", data["category"])
        self.assertEqual("Testing FTW", data["comments"])
