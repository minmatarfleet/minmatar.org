"""The Structures tab row: owner alliance and its ticker."""

from django.contrib.auth.models import User
from django.test import Client, TestCase

from campaigns.models import CampaignKind, CampaignParty, CampaignStructure
from campaigns.tests.helpers import KAMELA, auth_headers, grant, make_campaign
from eveonline.models import EveAlliance


class StructureOwnerTickerTestCase(TestCase):
    def setUp(self):
        self.campaign = make_campaign(kind=CampaignKind.STRATEGIC)
        self.viewer = User.objects.create(username="viewer")
        grant(self.viewer, "view_campaign")

    def _structure(self, name, **fields):
        return CampaignStructure.objects.create(
            campaign=self.campaign,
            name=name,
            structure_type="astrahus",
            solar_system_id=KAMELA,
            system_name="Kamela",
            **fields,
        )

    def _rows(self):
        response = Client().get(
            f"/api/campaigns/{self.campaign.slug}",
            **auth_headers(self.viewer),
        )
        self.assertEqual(response.status_code, 200)
        return {row["name"]: row for row in response.json()["structures"]}

    def test_ticker_from_alliance_table_then_parties(self):
        EveAlliance.objects.create(
            alliance_id=99000001, name="Example Alliance", ticker="EXA"
        )
        CampaignParty.objects.create(
            campaign=self.campaign,
            alliance_id=99000002,
            name="Other Alliance",
            ticker="OTH",
        )
        self._structure("Home One", alliance_id=99000001)
        self._structure(
            "Alt Corp Box",
            alliance_id=99000003,
            alliance_name="Alt Holding",
            related_alliance_id=99000002,
            related_alliance_name="Other Alliance",
        )
        self._structure(
            "Unknown", alliance_id=99000004, alliance_name="Nobody Known"
        )
        rows = self._rows()
        self.assertEqual(rows["Home One"]["owner_alliance_ticker"], "EXA")
        self.assertEqual(rows["Alt Corp Box"]["owner_alliance_id"], 99000002)
        self.assertEqual(rows["Alt Corp Box"]["owner_alliance_ticker"], "OTH")
        self.assertEqual(
            rows["Unknown"]["owner_alliance_ticker"], "Nobody Known"
        )
