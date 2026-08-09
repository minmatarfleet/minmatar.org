from django.test import Client, TestCase
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch

from eveonline.models import (
    EveCorporation,
    EveCorporationContract,
    EveLocation,
)

from buyback.models import (
    BUYBACK_CONTRACT_TYPE,
    BUYBACK_CORPORATION_ID,
    BuybackContract,
    EveBuybackSettings,
)

BASE_URL = "/api/buyback"


class BuybackContractProxyTestCase(TestCase):
    """Verify BuybackContract filters EveCorporationContract correctly."""

    def setUp(self):
        super().setUp()
        self.corp = EveCorporation.objects.create(
            corporation_id=BUYBACK_CORPORATION_ID,
            name="Minmatar Extraction Company",
            ticker="M-EXC",
        )
        self.other_corp = EveCorporation.objects.create(
            corporation_id=12345,
            name="Other Corp",
            ticker="OTH",
        )

    def _make_contract(self, corporation=None, **overrides):
        defaults = {
            "corporation": corporation or self.corp,
            "type": BUYBACK_CONTRACT_TYPE,
            "status": "outstanding",
            "issuer_id": 99999,
            "assignee_id": BUYBACK_CORPORATION_ID,
            "start_location_id": 100001,
            "end_location_id": 100001,
            "volume": 5000,
            "price": 100000000,
            "title": "https://janice.e-351.com/a/test",
            "date_issued": timezone.now(),
        }
        defaults.update(overrides)
        return EveCorporationContract.objects.create(**defaults)

    def test_proxy_filters_to_buyback_corporation(self):
        self._make_contract(contract_id=1)
        self._make_contract(contract_id=2, corporation=self.other_corp)
        self.assertEqual(BuybackContract.objects.count(), 1)
        self.assertEqual(BuybackContract.objects.first().contract_id, 1)

    def test_proxy_filters_to_item_exchange_type(self):
        self._make_contract(contract_id=1)
        self._make_contract(contract_id=2, type="courier")
        self.assertEqual(BuybackContract.objects.count(), 1)

    def test_proxy_filters_to_assignee(self):
        self._make_contract(contract_id=1)
        self._make_contract(contract_id=2, assignee_id=77777)
        self.assertEqual(BuybackContract.objects.count(), 1)

    def test_active_queryset(self):
        self._make_contract(contract_id=1, status="outstanding")
        self._make_contract(contract_id=2, status="in_progress")
        self._make_contract(contract_id=3, status="finished")
        self._make_contract(contract_id=4, status="expired")
        self.assertEqual(BuybackContract.objects.active().count(), 2)

    def test_finished_queryset(self):
        self._make_contract(contract_id=1, status="outstanding")
        self._make_contract(contract_id=2, status="finished")
        self._make_contract(contract_id=3, status="finished")
        self.assertEqual(BuybackContract.objects.finished().count(), 2)


class BuybackSettingsEndpointTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        super().setUp()
        self.location = EveLocation.objects.create(
            location_id=1044444444444,
            location_name="Amo - Minmatar Ore Reprocessing",
            solar_system_id=30002788,
            solar_system_name="Amo",
            short_name="Amo",
        )

    def test_get_settings_defaults(self):
        response = self.client.get(f"{BASE_URL}/settings")
        self.assertEqual(200, response.status_code)
        data = response.json()
        # Active requires a configured location.
        self.assertFalse(data["active"])
        self.assertEqual(data["corporation_id"], BUYBACK_CORPORATION_ID)
        self.assertEqual(data["assignee_name"], "Minmatar Extraction Company")
        self.assertTrue(
            any(
                "supply-chain" in category.lower()
                or "import" in category.lower()
                for category in data["accepted_categories"]
            )
        )
        self.assertEqual(data["exclusions"], [])
        self.assertEqual(data["accepted_items"], [])
        self.assertEqual(data["rate_rules"]["ore_refine"], 0.85)
        self.assertEqual(data["rate_rules"]["demand_jita_buy"], 1.0)
        self.assertEqual(data["rate_rules"]["surplus_jita_buy"], 0.9)
        self.assertIsNone(data["location"])

    def test_get_settings_with_location(self):
        settings = EveBuybackSettings.load()
        settings.location = self.location
        settings.save()
        response = self.client.get(f"{BASE_URL}/settings")
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertTrue(data["active"])
        self.assertEqual(
            data["location"]["name"], "Amo - Minmatar Ore Reprocessing"
        )
        self.assertEqual(data["location"]["short_name"], "Amo")
        self.assertEqual(
            data["location"]["location_id"], self.location.location_id
        )


class BuybackContractsEndpointTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        super().setUp()
        public_data = patch("eveonline.signals.update_character_public_data")
        public_data.start()
        self.addCleanup(public_data.stop)
        self.corp = EveCorporation.objects.create(
            corporation_id=BUYBACK_CORPORATION_ID,
            name="Minmatar Extraction Company",
            ticker="M-EXC",
        )
        EveLocation.objects.create(
            location_id=100001,
            location_name="Amo - Minmatar Ore Reprocessing",
            solar_system_id=30002788,
            solar_system_name="Amo",
            short_name="Amo",
        )

    def _make_contract(self, **overrides):
        defaults = {
            "corporation": self.corp,
            "type": BUYBACK_CONTRACT_TYPE,
            "status": "outstanding",
            "issuer_id": 99999,
            "assignee_id": BUYBACK_CORPORATION_ID,
            "start_location_id": 100001,
            "end_location_id": 100001,
            "volume": 5000,
            "price": 100000000,
            "title": "https://janice.e-351.com/a/test",
            "date_issued": timezone.now(),
        }
        defaults.update(overrides)
        return EveCorporationContract.objects.create(**defaults)

    def test_get_active_contracts(self):
        self._make_contract(contract_id=12345)
        response = self.client.get(f"{BASE_URL}/contracts")
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["contract_id"], 12345)
        self.assertEqual(data[0]["price"], 100000000)
        self.assertEqual(data[0]["location_name"], "Amo")
        self.assertEqual(data[0]["title"], "https://janice.e-351.com/a/test")

    def test_get_active_contracts_keeps_unknown_issuer(self):
        """External issuers may not exist as EveCharacter; still return the row."""
        self._make_contract(contract_id=12345, issuer_id=1825797880)
        response = self.client.get(f"{BASE_URL}/contracts")
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["contract_id"], 12345)
        self.assertEqual(data[0]["issuer_id"], 1825797880)
        self.assertEqual(data[0]["issuer_character_name"], "Unknown")

    def test_history_keeps_unknown_issuer(self):
        self._make_contract(
            contract_id=2,
            status="finished",
            issuer_id=1825797880,
            date_completed=timezone.now(),
        )
        response = self.client.get(f"{BASE_URL}/contracts/history")
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["issuer_id"], 1825797880)
        self.assertEqual(data[0]["issuer_character_name"], "Unknown")

    def test_history_returns_finished_only(self):
        self._make_contract(contract_id=1, status="outstanding")
        self._make_contract(
            contract_id=2,
            status="finished",
            date_completed=timezone.now(),
        )
        response = self.client.get(f"{BASE_URL}/contracts/history")
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["contract_id"], 2)

    def test_stats_in_out(self):
        self._make_contract(
            contract_id=1, status="outstanding", price=50_000_000
        )
        self._make_contract(
            contract_id=2,
            status="finished",
            price=75_000_000,
            date_issued=timezone.now() - timedelta(hours=2),
            date_completed=timezone.now(),
        )
        response = self.client.get(f"{BASE_URL}/contracts/stats")
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(data["outstanding_count"], 1)
        self.assertEqual(data["outstanding_isk"], 50_000_000)
        self.assertEqual(data["finished_count"], 1)
        self.assertEqual(data["finished_isk"], 75_000_000)
        self.assertIsNotNone(data["average_processing_seconds"])
        self.assertEqual(data["window_days"], 30)
