"""Tests for buyback stock ledger helpers and endpoints."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import Client, TestCase
from django.utils import timezone

from buyback.helpers.contracts_ledger import (
    classify_contract_direction,
    upsert_ledger_from_contract_items,
)
from buyback.helpers.hangar import quantities_from_assets
from buyback.helpers.metrics import assign_demand_statuses
from buyback.helpers.sell_orders import sync_sold_order_ledger_entries
from buyback.helpers.unknown import emit_unknown_from_snapshots
from buyback.models import (
    BUYBACK_CONTRACT_TYPE,
    BUYBACK_CORPORATION_ID,
    BuybackAcceptedItem,
    BuybackHangarSnapshot,
    BuybackLedgerEntry,
    EveBuybackSettings,
)
from buyback.tests.helpers import BASE_URL, ensure_type
from eveonline.models import (
    EveCorporation,
    EveCorporationContract,
    EveLocation,
)


class HangarQuantitiesTestCase(TestCase):
    def test_sums_deliveries_and_director_hangar(self):
        settings = EveBuybackSettings.load()
        settings.stockpile_structure_id = 100
        settings.stockpile_office_id = 200
        settings.stockpile_hangar_flag = "CorpSAG1"
        settings.stockpile_include_deliveries = True
        settings.save()

        assets = [
            {
                "type_id": 1,
                "quantity": 10,
                "location_id": 100,
                "location_flag": "CorpDeliveries",
            },
            {
                "type_id": 1,
                "quantity": 5,
                "location_id": 200,
                "location_flag": "CorpSAG1",
            },
            {
                "type_id": 2,
                "quantity": 99,
                "location_id": 200,
                "location_flag": "CorpSAG2",
            },
        ]
        totals = quantities_from_assets(assets, settings=settings)
        self.assertEqual(totals, {1: 15})


class ContractDirectionTestCase(TestCase):
    def setUp(self):
        self.corp = EveCorporation.objects.create(
            corporation_id=BUYBACK_CORPORATION_ID,
            name="M-EXC",
            ticker="M-EXC",
        )

    def _make_contract(self, **overrides):
        defaults = {
            "corporation": self.corp,
            "type": BUYBACK_CONTRACT_TYPE,
            "status": "finished",
            "issuer_id": 1,
            "assignee_id": BUYBACK_CORPORATION_ID,
            "date_issued": timezone.now(),
            "volume": 1,
            "price": 0,
        }
        defaults.update(overrides)
        return EveCorporationContract.objects.create(**defaults)

    def test_in_and_out_classification(self):
        inbound = self._make_contract(contract_id=1)
        outbound = self._make_contract(
            contract_id=2,
            assignee_id=98733885,
            issuer_corporation_id=BUYBACK_CORPORATION_ID,
        )
        self.assertEqual(
            classify_contract_direction(inbound),
            BuybackLedgerEntry.Reason.IN_CONTRACT,
        )
        self.assertEqual(
            classify_contract_direction(outbound),
            BuybackLedgerEntry.Reason.SOLD_CONTRACT,
        )


class ContractLedgerUpsertTestCase(TestCase):
    def setUp(self):
        self.corp = EveCorporation.objects.create(
            corporation_id=BUYBACK_CORPORATION_ID,
            name="M-EXC",
            ticker="M-EXC",
        )
        self.eve_type = ensure_type(
            type_id=62518,
            name="Compressed Veldspar",
            group_id=462,
            group_name="Veldspar",
            category_id=25,
            category_name="Asteroid",
        )
        self.contract = EveCorporationContract.objects.create(
            contract_id=234840893,
            corporation=self.corp,
            type=BUYBACK_CONTRACT_TYPE,
            status="finished",
            assignee_id=BUYBACK_CORPORATION_ID,
            issuer_id=1,
            issuer_corporation_id=999,
            date_issued=timezone.now(),
            date_completed=timezone.now(),
            price=100,
            volume=1,
            start_location_id=1040765104287,
        )

    def test_upsert_in_contract_items(self):
        created = upsert_ledger_from_contract_items(
            contract=self.contract,
            reason=BuybackLedgerEntry.Reason.IN_CONTRACT,
            items=[
                {
                    "type_id": self.eve_type.id,
                    "quantity": 1000,
                    "record_id": 99,
                    "is_included": True,
                }
            ],
        )
        self.assertEqual(created, 1)
        entry = BuybackLedgerEntry.objects.get()
        self.assertEqual(entry.reason, BuybackLedgerEntry.Reason.IN_CONTRACT)
        self.assertEqual(entry.quantity, 1000)
        self.assertEqual(entry.source_id, "234840893:99")
        self.assertEqual(entry.counterparty_id, 1)
        self.assertTrue(entry.counterparty_name)


class UnknownResidualTestCase(TestCase):
    def setUp(self):
        self.eve_type = ensure_type(
            type_id=62518,
            name="Compressed Veldspar",
            group_id=462,
            group_name="Veldspar",
            category_id=25,
            category_name="Asteroid",
        )

    def test_unexplained_drop_becomes_unknown(self):
        t0 = timezone.now() - timedelta(hours=1)
        t1 = timezone.now()
        previous = BuybackHangarSnapshot.objects.create(
            taken_at=t0,
            quantities={str(self.eve_type.id): 1000},
        )
        current = BuybackHangarSnapshot.objects.create(
            taken_at=t1,
            quantities={str(self.eve_type.id): 400},
        )
        BuybackLedgerEntry.objects.create(
            reason=BuybackLedgerEntry.Reason.SOLD_CONTRACT,
            eve_type=self.eve_type,
            quantity=200,
            occurred_at=t0 + timedelta(minutes=10),
            source_id="sold:1",
        )
        BuybackLedgerEntry.objects.create(
            reason=BuybackLedgerEntry.Reason.IN_CONTRACT,
            eve_type=self.eve_type,
            quantity=50,
            occurred_at=t0 + timedelta(minutes=5),
            source_id="in:1",
        )
        result = emit_unknown_from_snapshots(previous, current)
        self.assertEqual(result["created"], 1)
        unknown = BuybackLedgerEntry.objects.get(
            reason=BuybackLedgerEntry.Reason.UNKNOWN
        )
        self.assertEqual(unknown.quantity, 450)


class SellOrderLedgerTestCase(TestCase):
    def setUp(self):
        self.eve_type = ensure_type(
            type_id=34,
            name="Tritanium",
            group_id=18,
            group_name="Mineral",
            category_id=4,
            category_name="Material",
        )

    @patch("buyback.helpers.sell_orders.fetch_wallet_transactions")
    def test_sync_sold_order_from_wallet_tx(self, mock_fetch):
        mock_fetch.return_value = [
            {
                "transaction_id": 555,
                "type_id": self.eve_type.id,
                "quantity": 100,
                "is_buy": False,
                "unit_price": "10.5",
                "date": timezone.now().isoformat(),
                "location_id": 1040765104287,
            },
            {
                "transaction_id": 556,
                "type_id": self.eve_type.id,
                "quantity": 50,
                "is_buy": True,
                "unit_price": "9",
                "date": timezone.now().isoformat(),
            },
        ]
        result = sync_sold_order_ledger_entries()
        self.assertEqual(result["created"], 1)
        entry = BuybackLedgerEntry.objects.get(
            reason=BuybackLedgerEntry.Reason.SOLD_ORDER
        )
        self.assertEqual(entry.quantity, 100)
        self.assertEqual(entry.source_id, "555")


class DemandStatusAssignmentTestCase(TestCase):
    def test_median_split(self):
        statuses = assign_demand_statuses({1: 0, 2: 10, 3: 20, 4: 100})
        self.assertEqual(statuses[1], BuybackAcceptedItem.DemandStatus.SURPLUS)
        self.assertEqual(statuses[2], BuybackAcceptedItem.DemandStatus.LOW)
        self.assertEqual(statuses[3], BuybackAcceptedItem.DemandStatus.LOW)
        self.assertEqual(statuses[4], BuybackAcceptedItem.DemandStatus.HIGH)


class StockAndLedgerEndpointTestCase(TestCase):
    def setUp(self):
        location = EveLocation.objects.create(
            location_id=1040765104287,
            location_name="Amo - Minmatar Ore Reprocessing",
            short_name="Amo",
            solar_system_id=30002053,
            solar_system_name="Amo",
        )
        settings = EveBuybackSettings.load()
        settings.location = location
        settings.active = True
        settings.save()
        self.eve_type = ensure_type(
            type_id=62518,
            name="Compressed Veldspar",
            group_id=462,
            group_name="Veldspar",
            category_id=25,
            category_name="Asteroid",
        )
        BuybackAcceptedItem.objects.create(
            eve_type=self.eve_type,
            category=BuybackAcceptedItem.Category.ORE,
            active=True,
            demand_status=BuybackAcceptedItem.DemandStatus.HIGH,
            demand_quantity=50,
            stockpile_quantity=123,
            metrics_updated_at=timezone.now(),
        )
        BuybackHangarSnapshot.objects.create(
            taken_at=timezone.now(),
            quantities={str(self.eve_type.id): 123},
        )
        BuybackLedgerEntry.objects.create(
            reason=BuybackLedgerEntry.Reason.IN_CONTRACT,
            eve_type=self.eve_type,
            quantity=50,
            occurred_at=timezone.now(),
            source_id="c:1",
        )
        self.client = Client()

    def test_stock_endpoint(self):
        response = self.client.get(f"{BASE_URL}/stock")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["quantity"], 123)
        self.assertIn("isk_value", data["items"][0])

    def test_ledger_endpoint(self):
        response = self.client.get(f"{BASE_URL}/ledger")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["entries"][0]["reason"], "in_contract")

    @patch("buyback.helpers.stock_stats.fetch_corporation_wallet_balance")
    @patch("buyback.helpers.stock_stats.batch_estimate_guide_isk")
    def test_stock_stats_endpoint(self, mock_estimate, mock_wallet):
        mock_estimate.side_effect = lambda rows: [1_000_000.0 for _ in rows]
        mock_wallet.return_value = 2_500_000_000
        BuybackLedgerEntry.objects.create(
            reason=BuybackLedgerEntry.Reason.SOLD_CONTRACT,
            eve_type=self.eve_type,
            quantity=10,
            occurred_at=timezone.now(),
            isk_total=Decimal("5000000"),
            source_id="out:1",
        )
        response = self.client.get(f"{BASE_URL}/stock/stats")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["stockpile_value"], 1_000_000)
        self.assertEqual(data["remaining_isk"], 2_500_000_000)
        self.assertEqual(data["turnover_value"], 5_000_000)
        self.assertEqual(data["window_days"], 30)

    def test_settings_includes_stockpile_and_demand_status(self):
        response = self.client.get(f"{BASE_URL}/settings")
        self.assertEqual(response.status_code, 200)
        item = response.json()["accepted_items"][0]
        self.assertEqual(item["demand_status"], "high")
        self.assertEqual(item["stockpile_quantity"], 123)
        self.assertTrue(item["in_demand"])


class StoredDemandAppraisalTestCase(TestCase):
    @patch("buyback.helpers.appraise.get_baseline_buy_prices")
    @patch("buyback.helpers.appraise.get_baseline_buy_prices_by_name")
    @patch("buyback.helpers.pricing.ore_materials_per_portion")
    def test_appraisal_uses_stored_demand(
        self, mock_portion, mock_by_name, mock_by_id
    ):
        mock_by_id.return_value = {}
        mock_by_name.return_value = {"Tritanium": Decimal("5")}
        mock_portion.return_value = {"Tritanium": 415}
        location = EveLocation.objects.create(
            location_id=1,
            location_name="Amo",
            short_name="Amo",
            solar_system_id=30002053,
            solar_system_name="Amo",
        )
        settings = EveBuybackSettings.load()
        settings.location = location
        settings.active = True
        settings.save()
        ore = ensure_type(
            type_id=62518,
            name="Compressed Veldspar",
            group_id=462,
            group_name="Veldspar",
            category_id=25,
            category_name="Asteroid",
        )
        BuybackAcceptedItem.objects.create(
            eve_type=ore,
            category=BuybackAcceptedItem.Category.ORE,
            active=True,
            demand_status=BuybackAcceptedItem.DemandStatus.SURPLUS,
            demand_quantity=0,
        )
        response = Client().post(
            f"{BASE_URL}/appraise",
            data={"paste": "Compressed Veldspar\t100"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        line = response.json()["lines"][0]
        self.assertTrue(line["accepted"])
        self.assertEqual(line["rate_reason"], "accepted_surplus")
