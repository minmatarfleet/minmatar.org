"""Edge-case tests for buyback ledger, contracts, reservations, and stockpile math."""

from datetime import timedelta
from decimal import Decimal

from django.test import Client
from django.utils import timezone

from app.test import TestCase
from buyback.helpers.contracts_ledger import upsert_ledger_from_contract_items
from buyback.helpers.purchase_orders import (
    PurchaseOrderError,
    cancel_purchase_order,
    complete_purchase_order,
    try_complete_from_outbound_contracts,
)
from buyback.helpers.remaining import (
    available_stock_quantities,
    remaining_sale_quantities,
)
from buyback.helpers.unknown import emit_unknown_from_snapshots
from buyback.models import (
    BUYBACK_CONTRACT_TYPE,
    BUYBACK_CORPORATION_ID,
    BuybackHangarSnapshot,
    BuybackLedgerEntry,
    BuybackPurchaseOrder,
    SellPriceBasis,
)
from buyback.tests.helpers import BASE_URL, ensure_type
from eveonline.models import (
    EveCharacter,
    EveCorporation,
    EveCorporationContract,
    EveLocation,
)
from market.models import EveMarketItemLocationPrice


def _ledger(*, eve_type, quantity, reason, source_id, **extra):
    defaults = {
        "reason": reason,
        "eve_type": eve_type,
        "quantity": quantity,
        "occurred_at": timezone.now(),
        "source_id": source_id,
    }
    defaults.update(extra)
    return BuybackLedgerEntry.objects.create(**defaults)


class StockpileEdgeCaseBase(TestCase):
    """50 Water in ledger; optional hangar snapshot."""

    def setUp(self):
        super().setUp()
        self.setup_character()
        self.water = ensure_type(
            type_id=3645,
            name="Water",
            group_id=1042,
            group_name="Basic Commodities - Tier 1",
            category_id=43,
            category_name="Planetary Commodities",
        )
        jita = EveLocation.objects.create(
            location_id=60003760,
            location_name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
            solar_system_id=30000142,
            solar_system_name="Jita",
            short_name="Jita",
            region_id=10000002,
            price_baseline=True,
            prices_active=True,
            market_active=False,
        )
        EveMarketItemLocationPrice.objects.create(
            location=jita,
            item=self.water,
            buy_price=Decimal("100.00"),
            sell_price=Decimal("100.00"),
            split_price=Decimal("100.00"),
        )
        _ledger(
            eve_type=self.water,
            quantity=50,
            reason=BuybackLedgerEntry.Reason.IN_CONTRACT,
            source_id="in:water",
        )
        BuybackHangarSnapshot.objects.create(
            taken_at=timezone.now(),
            quantities={str(self.water.id): 50},
        )

    def _place(self, qty: int = 10) -> BuybackPurchaseOrder:
        order = BuybackPurchaseOrder.objects.create(
            status=BuybackPurchaseOrder.Status.PENDING,
            created_by=self.user,
            character_id=123456,
            character_name="Test Char",
            paste=f"Water\t{qty}",
            contract_total=qty * 100,
            sell_price_basis=SellPriceBasis.JITA_SPLIT,
            sell_markup=0,
        )
        order.lines.create(
            eve_type=self.water,
            name=self.water.name,
            quantity=qty,
            unit_price=Decimal("100.00"),
            line_total=Decimal(qty * 100),
        )
        return order

    def _outbound(
        self,
        order: BuybackPurchaseOrder,
        qty: int,
        *,
        source_id: str,
        when=None,
    ):
        return _ledger(
            eve_type=self.water,
            quantity=qty,
            reason=BuybackLedgerEntry.Reason.SOLD_CONTRACT,
            source_id=source_id,
            counterparty_id=order.character_id,
            occurred_at=when or timezone.now(),
        )


class ContractClosingStockpileTestCase(StockpileEdgeCaseBase):
    """Contract sync closes the loop: ledger out → reservation release on complete."""

    def test_outbound_contract_reduces_sellable_pool(self):
        self.assertEqual(remaining_sale_quantities()[self.water.id], 50)
        _ledger(
            eve_type=self.water,
            quantity=15,
            reason=BuybackLedgerEntry.Reason.SOLD_CONTRACT,
            source_id="out:early",
            counterparty_id=999,
        )
        self.assertEqual(remaining_sale_quantities()[self.water.id], 35)

    def test_place_then_outbound_then_auto_complete(self):
        order = self._place(10)
        self.assertEqual(remaining_sale_quantities()[self.water.id], 40)
        self._outbound(order, 10, source_id="out:close")
        self.assertEqual(try_complete_from_outbound_contracts(), 1)
        order.refresh_from_db()
        self.assertEqual(order.status, BuybackPurchaseOrder.Status.COMPLETED)
        # Reservation released; one outbound contract of 10 → 50 in − 10 out
        self.assertEqual(remaining_sale_quantities()[self.water.id], 40)

    def test_cancel_before_contract_sync_releases_reservation(self):
        order = self._place(10)
        self.assertEqual(remaining_sale_quantities()[self.water.id], 40)
        cancel_purchase_order(order)
        self.assertEqual(remaining_sale_quantities()[self.water.id], 50)
        self.assertEqual(try_complete_from_outbound_contracts(), 0)

    def test_complete_after_cancel_is_rejected(self):
        order = self._place(10)
        cancel_purchase_order(order)
        with self.assertRaises(PurchaseOrderError):
            complete_purchase_order(order, self.user)

    def test_double_cancel_rejected(self):
        order = self._place(10)
        cancel_purchase_order(order)
        with self.assertRaises(PurchaseOrderError):
            cancel_purchase_order(order)

    def test_cancel_after_complete_rejected(self):
        order = self._place(10)
        self._outbound(order, 10, source_id="out:cancel-block")
        complete_purchase_order(order, self.user)
        with self.assertRaises(PurchaseOrderError):
            cancel_purchase_order(order)

    def test_contract_upsert_is_idempotent(self):
        corp = EveCorporation.objects.create(
            corporation_id=BUYBACK_CORPORATION_ID,
            name="M-EXC",
            ticker="M-EXC",
        )
        contract = EveCorporationContract.objects.create(
            contract_id=9001,
            corporation=corp,
            type=BUYBACK_CONTRACT_TYPE,
            status="finished",
            assignee_id=BUYBACK_CORPORATION_ID,
            issuer_id=111,
            issuer_corporation_id=222,
            date_issued=timezone.now(),
            date_completed=timezone.now(),
            price=0,
            volume=1,
        )
        items = [
            {
                "type_id": self.water.id,
                "quantity": 5,
                "record_id": 1,
                "is_included": True,
            }
        ]
        self.assertEqual(
            upsert_ledger_from_contract_items(
                contract=contract,
                reason=BuybackLedgerEntry.Reason.IN_CONTRACT,
                items=items,
            ),
            1,
        )
        self.assertEqual(
            upsert_ledger_from_contract_items(
                contract=contract,
                reason=BuybackLedgerEntry.Reason.IN_CONTRACT,
                items=items,
            ),
            0,
        )
        self.assertEqual(BuybackLedgerEntry.objects.count(), 2)
        entry = BuybackLedgerEntry.objects.get(source_id="9001:1")
        self.assertEqual(entry.quantity, 5)


class FifoAutoCompleteEdgeCaseTestCase(StockpileEdgeCaseBase):
    def test_contract_before_order_created_does_not_complete(self):
        order = self._place(10)
        self._outbound(
            order,
            10,
            source_id="out:old",
            when=order.created_at - timedelta(hours=1),
        )
        self.assertEqual(try_complete_from_outbound_contracts(), 0)

    def test_wrong_pilot_contract_does_not_complete(self):
        self._place(10)
        _ledger(
            eve_type=self.water,
            quantity=10,
            reason=BuybackLedgerEntry.Reason.SOLD_CONTRACT,
            source_id="out:wrong-pilot",
            counterparty_id=999999,
            occurred_at=timezone.now(),
        )
        self.assertEqual(try_complete_from_outbound_contracts(), 0)

    def test_partial_contract_covers_first_order_only(self):
        first = self._place(10)
        second = self._place(10)
        self._outbound(first, 15, source_id="out:partial")
        completed = try_complete_from_outbound_contracts()
        self.assertEqual(completed, 1)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, BuybackPurchaseOrder.Status.COMPLETED)
        self.assertEqual(second.status, BuybackPurchaseOrder.Status.PENDING)

    def test_two_orders_one_full_contract_fifo_order(self):
        first = self._place(10)
        second = self._place(10)
        self._outbound(first, 10, source_id="out:exact")
        self.assertEqual(try_complete_from_outbound_contracts(), 1)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, BuybackPurchaseOrder.Status.COMPLETED)
        self.assertEqual(second.status, BuybackPurchaseOrder.Status.PENDING)

    def test_second_order_cannot_steal_contract_on_manual_complete(self):
        first = self._place(10)
        second = self._place(10)
        self._outbound(first, 10, source_id="out:steal-test")
        with self.assertRaises(PurchaseOrderError):
            complete_purchase_order(second, self.user)
        complete_purchase_order(first, self.user)
        second.refresh_from_db()
        self.assertEqual(second.status, BuybackPurchaseOrder.Status.PENDING)

    def test_auto_complete_idempotent(self):
        order = self._place(10)
        self._outbound(order, 10, source_id="out:idempotent")
        self.assertEqual(try_complete_from_outbound_contracts(), 1)
        self.assertEqual(try_complete_from_outbound_contracts(), 0)

    def test_double_complete_rejected(self):
        order = self._place(10)
        self._outbound(order, 10, source_id="out:double")
        complete_purchase_order(order, self.user)
        with self.assertRaises(PurchaseOrderError):
            complete_purchase_order(order, self.user)

    def test_contract_to_buyer_corporation_completes(self):
        EveCharacter.objects.filter(character_id=123456).update(
            corporation_id=98832280
        )
        order = self._place(10)
        _ledger(
            eve_type=self.water,
            quantity=10,
            reason=BuybackLedgerEntry.Reason.SOLD_CONTRACT,
            source_id="out:buyer-corp",
            counterparty_id=98832280,
            occurred_at=timezone.now(),
        )
        self.assertEqual(try_complete_from_outbound_contracts(), 1)
        order.refresh_from_db()
        self.assertEqual(order.status, BuybackPurchaseOrder.Status.COMPLETED)

    def test_contract_to_buyer_alt_completes(self):
        EveCharacter.objects.create(
            character_id=222222,
            character_name="Alt Char",
            user=self.user,
        )
        order = self._place(10)
        _ledger(
            eve_type=self.water,
            quantity=10,
            reason=BuybackLedgerEntry.Reason.SOLD_CONTRACT,
            source_id="out:buyer-alt",
            counterparty_id=222222,
            occurred_at=timezone.now(),
        )
        self.assertEqual(try_complete_from_outbound_contracts(), 1)
        order.refresh_from_db()
        self.assertEqual(order.status, BuybackPurchaseOrder.Status.COMPLETED)

    def test_contract_to_ceo_corporation_completes(self):
        char = EveCharacter.objects.get(character_id=123456)
        EveCorporation.objects.create(
            corporation_id=5550001,
            name="Owned Corp",
            ceo=char,
        )
        order = self._place(10)
        _ledger(
            eve_type=self.water,
            quantity=10,
            reason=BuybackLedgerEntry.Reason.SOLD_CONTRACT,
            source_id="out:ceo-corp",
            counterparty_id=5550001,
            occurred_at=timezone.now(),
        )
        self.assertEqual(try_complete_from_outbound_contracts(), 1)
        order.refresh_from_db()
        self.assertEqual(order.status, BuybackPurchaseOrder.Status.COMPLETED)


class HangarCapEdgeCaseTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.ore = ensure_type(
            type_id=62518,
            name="Compressed Veldspar",
            group_id=462,
            group_name="Veldspar",
            category_id=25,
            category_name="Asteroid",
        )

    def test_hangar_caps_ledger_when_physical_is_lower(self):
        _ledger(
            eve_type=self.ore,
            quantity=1000,
            reason=BuybackLedgerEntry.Reason.IN_CONTRACT,
            source_id="in:1",
        )
        BuybackHangarSnapshot.objects.create(
            taken_at=timezone.now(),
            quantities={str(self.ore.id): 200},
        )
        self.assertEqual(remaining_sale_quantities()[self.ore.id], 200)
        self.assertEqual(available_stock_quantities()[self.ore.id], 200)

    def test_unknown_rows_do_not_break_hangar_cap(self):
        _ledger(
            eve_type=self.ore,
            quantity=1000,
            reason=BuybackLedgerEntry.Reason.IN_CONTRACT,
            source_id="in:1",
        )
        _ledger(
            eve_type=self.ore,
            quantity=300,
            reason=BuybackLedgerEntry.Reason.UNKNOWN,
            source_id="unk:1",
        )
        BuybackHangarSnapshot.objects.create(
            taken_at=timezone.now(),
            quantities={str(self.ore.id): 150},
        )
        self.assertEqual(remaining_sale_quantities()[self.ore.id], 150)

    def test_snapshot_drop_with_explained_outflow_no_unknown(self):
        t0 = timezone.now() - timedelta(hours=2)
        t1 = timezone.now()
        previous = BuybackHangarSnapshot.objects.create(
            taken_at=t0,
            quantities={str(self.ore.id): 1000},
        )
        current = BuybackHangarSnapshot.objects.create(
            taken_at=t1,
            quantities={str(self.ore.id): 700},
        )
        BuybackLedgerEntry.objects.create(
            reason=BuybackLedgerEntry.Reason.SOLD_CONTRACT,
            eve_type=self.ore,
            quantity=300,
            occurred_at=t0 + timedelta(minutes=30),
            source_id="sold:explained",
        )
        result = emit_unknown_from_snapshots(previous, current)
        self.assertEqual(result["created"], 0)
        self.assertFalse(
            BuybackLedgerEntry.objects.filter(
                reason=BuybackLedgerEntry.Reason.UNKNOWN
            ).exists()
        )


class ReservationStatusEdgeCaseTestCase(StockpileEdgeCaseBase):
    def test_completed_order_does_not_hold_reservation(self):
        order = self._place(10)
        self._outbound(order, 10, source_id="out:done")
        complete_purchase_order(order, self.user)
        self.assertEqual(remaining_sale_quantities()[self.water.id], 40)

    def test_cancelled_order_does_not_hold_reservation(self):
        order = self._place(10)
        cancel_purchase_order(order)
        self.assertEqual(remaining_sale_quantities()[self.water.id], 50)

    def test_available_stock_tracks_pending_reservation(self):
        order = self._place(10)
        self.assertEqual(available_stock_quantities()[self.water.id], 40)
        cancel_purchase_order(order)
        self.assertEqual(available_stock_quantities()[self.water.id], 50)


class MultiLineOrderEdgeCaseTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.setup_character()
        self.water = ensure_type(
            type_id=3645,
            name="Water",
            group_id=1042,
            group_name="Basic Commodities - Tier 1",
            category_id=43,
            category_name="Planetary Commodities",
        )
        self.bio = ensure_type(
            type_id=2329,
            name="Biocells",
            group_id=1042,
            group_name="Basic Commodities - Tier 1",
            category_id=43,
            category_name="Planetary Commodities",
        )
        for eve_type, qty in ((self.water, 50), (self.bio, 50)):
            _ledger(
                eve_type=eve_type,
                quantity=qty,
                reason=BuybackLedgerEntry.Reason.IN_CONTRACT,
                source_id=f"in:{eve_type.id}",
            )

    def test_partial_outbound_does_not_complete_multi_line_order(self):
        order = BuybackPurchaseOrder.objects.create(
            status=BuybackPurchaseOrder.Status.PENDING,
            created_by=self.user,
            character_id=123456,
            character_name="Test Char",
            paste="Water\t10\nBiocells\t10",
            contract_total=2000,
            sell_price_basis=SellPriceBasis.JITA_SPLIT,
            sell_markup=0,
        )
        for eve_type, qty in ((self.water, 10), (self.bio, 10)):
            order.lines.create(
                eve_type=eve_type,
                name=eve_type.name,
                quantity=qty,
                unit_price=Decimal("100.00"),
                line_total=Decimal("1000.00"),
            )
        _ledger(
            eve_type=self.water,
            quantity=10,
            reason=BuybackLedgerEntry.Reason.SOLD_CONTRACT,
            source_id="out:water-only",
            counterparty_id=123456,
        )
        self.assertEqual(try_complete_from_outbound_contracts(), 0)
        _ledger(
            eve_type=self.bio,
            quantity=10,
            reason=BuybackLedgerEntry.Reason.SOLD_CONTRACT,
            source_id="out:bio",
            counterparty_id=123456,
        )
        self.assertEqual(try_complete_from_outbound_contracts(), 1)

    def test_manual_complete_accepts_partial_outbound(self):
        order = BuybackPurchaseOrder.objects.create(
            status=BuybackPurchaseOrder.Status.PENDING,
            created_by=self.user,
            character_id=123456,
            character_name="Test Char",
            paste="Water\t10\nBiocells\t10",
            contract_total=2000,
            sell_price_basis=SellPriceBasis.JITA_SPLIT,
            sell_markup=0,
        )
        for eve_type, qty in ((self.water, 10), (self.bio, 10)):
            order.lines.create(
                eve_type=eve_type,
                name=eve_type.name,
                quantity=qty,
                unit_price=Decimal("100.00"),
                line_total=Decimal("1000.00"),
            )
        _ledger(
            eve_type=self.water,
            quantity=6,
            reason=BuybackLedgerEntry.Reason.SOLD_CONTRACT,
            source_id="out:water-partial",
            counterparty_id=123456,
        )
        complete_purchase_order(order, self.user)
        order.refresh_from_db()
        self.assertEqual(order.status, BuybackPurchaseOrder.Status.COMPLETED)
        lines = list(order.lines.all())
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0].eve_type_id, self.water.id)
        self.assertEqual(lines[0].quantity, 6)
        self.assertEqual(order.contract_total, 600)
        self.assertEqual(remaining_sale_quantities()[self.water.id], 44)
        self.assertEqual(remaining_sale_quantities()[self.bio.id], 50)


class ConcurrentPlaceEdgeCaseTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.setup_character()
        self.client = Client()
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}
        self.water = ensure_type(
            type_id=3645,
            name="Water",
            group_id=1042,
            group_name="Basic Commodities - Tier 1",
            category_id=43,
            category_name="Planetary Commodities",
        )
        jita = EveLocation.objects.create(
            location_id=60003760,
            location_name="Jita",
            solar_system_id=30000142,
            solar_system_name="Jita",
            short_name="Jita",
            region_id=10000002,
            price_baseline=True,
            prices_active=True,
            market_active=False,
        )
        EveMarketItemLocationPrice.objects.create(
            location=jita,
            item=self.water,
            buy_price=Decimal("100.00"),
            sell_price=Decimal("100.00"),
            split_price=Decimal("100.00"),
        )
        _ledger(
            eve_type=self.water,
            quantity=50,
            reason=BuybackLedgerEntry.Reason.IN_CONTRACT,
            source_id="in:water",
        )

    def test_cannot_oversell_last_unit_after_first_reservation(self):
        first = self.client.post(
            f"{BASE_URL}/stock/orders",
            data={"paste": "Water\t50", "source": "stockpile"},
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(first.status_code, 201)
        second = self.client.post(
            f"{BASE_URL}/stock/orders",
            data={"paste": "Water\t50", "source": "stockpile"},
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(second.status_code, 400)
        self.assertEqual(
            BuybackPurchaseOrder.objects.filter(
                status=BuybackPurchaseOrder.Status.PENDING
            ).count(),
            1,
        )


class LedgerAppendOnlyEdgeCaseTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.setup_character()
        self.ore = ensure_type(
            type_id=62518,
            name="Compressed Veldspar",
            group_id=462,
            group_name="Veldspar",
            category_id=25,
            category_name="Asteroid",
        )

    def test_cancel_does_not_delete_ledger_rows(self):
        _ledger(
            eve_type=self.ore,
            quantity=100,
            reason=BuybackLedgerEntry.Reason.IN_CONTRACT,
            source_id="in:1",
        )
        order = BuybackPurchaseOrder.objects.create(
            created_by=self.user,
            paste="x",
            contract_total=1,
            sell_price_basis=SellPriceBasis.JITA_SPLIT,
            sell_markup=0,
        )
        cancel_purchase_order(order)
        self.assertEqual(
            BuybackLedgerEntry.objects.filter(
                reason=BuybackLedgerEntry.Reason.IN_CONTRACT
            ).count(),
            1,
        )

    def test_sold_order_does_not_reduce_remaining_sale(self):
        _ledger(
            eve_type=self.ore,
            quantity=100,
            reason=BuybackLedgerEntry.Reason.IN_CONTRACT,
            source_id="in:1",
        )
        _ledger(
            eve_type=self.ore,
            quantity=40,
            reason=BuybackLedgerEntry.Reason.SOLD_ORDER,
            source_id="mkt:1",
        )
        self.assertEqual(remaining_sale_quantities()[self.ore.id], 100)
