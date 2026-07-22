from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.utils import timezone

from app.test import TestCase
from eveonline.models import EveLocation
from market.tests.test_fitting_expectations import _make_eve_type
from market.helpers.inferred_sales import (
    SnapshotOrder,
    infer_sales_from_snapshots,
    velocity_stats,
)
from market.helpers.order_book_sync import apply_order_book_snapshot
from market.models import (
    EveMarketInferredSale,
    EveMarketItemOrder,
    EveMarketOrderBookSync,
)


def _sell(
    order_id: int,
    type_id: int,
    price,
    volume: int,
    *,
    issued=None,
    duration_days=None,
) -> SnapshotOrder:
    return SnapshotOrder(
        order_id=order_id,
        type_id=type_id,
        price=Decimal(str(price)),
        volume_remain=volume,
        is_buy_order=False,
        issued=issued,
        duration_days=duration_days,
    )


class InferSalesFromSnapshotsTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.now = timezone.now()
        self.synced = self.now - timedelta(minutes=10)

    def test_partial_fill_exact_delta(self):
        previous = [_sell(1, 34, 5.0, 100)]
        current = [_sell(1, 34, 5.0, 60)]
        drafts = infer_sales_from_snapshots(
            previous, current, self.synced, self.now, baseline_by_type={34: 5}
        )
        self.assertEqual(len(drafts), 1)
        self.assertEqual(drafts[0].quantity, 40)
        self.assertEqual(
            drafts[0].reason, EveMarketInferredSale.REASON_PARTIAL_FILL
        )
        self.assertEqual(drafts[0].price, Decimal("5.0"))

    def test_vanished_cheapest_is_sale(self):
        previous = [
            _sell(1, 34, 5.0, 50),
            _sell(2, 34, 6.0, 50),
        ]
        current = [_sell(2, 34, 6.0, 50)]
        drafts = infer_sales_from_snapshots(
            previous, current, self.synced, self.now, baseline_by_type={34: 5}
        )
        self.assertEqual(len(drafts), 1)
        self.assertEqual(drafts[0].order_id, 1)
        self.assertEqual(drafts[0].quantity, 50)
        self.assertEqual(
            drafts[0].reason, EveMarketInferredSale.REASON_SELLOUT
        )

    def test_vanished_expensive_no_sale(self):
        previous = [
            _sell(1, 34, 5.0, 50),
            _sell(2, 34, 6.0, 50),
        ]
        current = [_sell(1, 34, 5.0, 50)]
        drafts = infer_sales_from_snapshots(
            previous, current, self.synced, self.now, baseline_by_type={34: 5}
        )
        self.assertEqual(drafts, [])

    def test_expired_vanished_no_sale(self):
        issued = self.now - timedelta(days=100)
        previous = [_sell(1, 34, 5.0, 50, issued=issued, duration_days=90)]
        drafts = infer_sales_from_snapshots(
            previous, [], self.synced, self.now, baseline_by_type={34: 5}
        )
        self.assertEqual(drafts, [])

    def test_ten_x_baseline_no_sale(self):
        previous = [_sell(1, 34, 1000.0, 50)]
        drafts = infer_sales_from_snapshots(
            previous, [], self.synced, self.now, baseline_by_type={34: 5}
        )
        self.assertEqual(drafts, [])

    def test_gap_over_30m_rebaseline_zero_sales(self):
        previous = [_sell(1, 34, 5.0, 50)]
        old_sync = self.now - timedelta(minutes=45)
        drafts = infer_sales_from_snapshots(
            previous, [], old_sync, self.now, baseline_by_type={34: 5}
        )
        self.assertEqual(drafts, [])

    def test_gap_missing_watermark_zero_sales(self):
        previous = [_sell(1, 34, 5.0, 50)]
        drafts = infer_sales_from_snapshots(
            previous, [], None, self.now, baseline_by_type={34: 5}
        )
        self.assertEqual(drafts, [])

    def test_ignores_buy_orders(self):
        previous = [
            SnapshotOrder(
                order_id=1,
                type_id=34,
                price=Decimal("5"),
                volume_remain=100,
                is_buy_order=True,
            )
        ]
        drafts = infer_sales_from_snapshots(
            previous, [], self.synced, self.now, baseline_by_type={34: 5}
        )
        self.assertEqual(drafts, [])


class VelocityStatsTestCase(TestCase):
    def test_fat_day_among_zeros_median_near_zero(self):
        buckets = [
            {"date": f"2026-01-{i:02d}", "units": 0} for i in range(1, 31)
        ]
        buckets[-1]["units"] = 500
        stats = velocity_stats(
            buckets, long_days=30, short_days=7, days_of_data=30
        )
        self.assertEqual(stats["median_daily_units"], 0.0)
        # Median is 0 so 4× cap does not apply; mean still finite.
        self.assertAlmostEqual(stats["short_mean_daily_units"], 500.0 / 7.0)

    def test_capped_mean_bounded_when_median_positive(self):
        buckets = [
            {"date": f"2026-01-{i:02d}", "units": 10} for i in range(1, 31)
        ]
        buckets[-1]["units"] = 1000
        stats = velocity_stats(
            buckets, long_days=30, short_days=7, days_of_data=30
        )
        self.assertEqual(stats["median_daily_units"], 10.0)
        # Cap at 4× median = 40; last 7 days: six 10s + one capped 40.
        self.assertAlmostEqual(
            stats["short_mean_daily_units"], (6 * 10 + 40) / 7.0
        )

    def test_fresh_install_effective_long_days_clamped(self):
        buckets = [
            {"date": f"2026-07-{i:02d}", "units": 10} for i in range(1, 31)
        ]
        stats = velocity_stats(
            buckets, long_days=30, short_days=7, days_of_data=2
        )
        self.assertEqual(stats["long_days"], 2)
        self.assertEqual(stats["days_of_data"], 2)


class ApplyOrderBookSnapshotTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.location = EveLocation.objects.create(
            location_id=9001,
            location_name="Test Hub",
            short_name="Hub",
            solar_system_id=1,
            solar_system_name="Test",
            market_active=True,
        )
        self.item = _make_eve_type(34, "Tritanium")
        self.now = timezone.now()

    def test_apply_persists_partial_fill_and_replaces_orders(self):
        EveMarketItemOrder.objects.create(
            order_id=1,
            item=self.item,
            location=self.location,
            price=Decimal("5.00"),
            quantity=100,
            is_buy_order=False,
            issued=self.now - timedelta(days=1),
            duration_days=90,
        )
        EveMarketOrderBookSync.objects.create(
            location=self.location,
            last_synced_at=self.now - timedelta(minutes=10),
        )

        with patch(
            "market.helpers.order_book_sync.get_prices_by_type_id",
            return_value={34: 5},
        ):
            sales, orders = apply_order_book_snapshot(
                self.location,
                [
                    {
                        "order_id": 1,
                        "type_id": 34,
                        "price": 5.0,
                        "volume_remain": 70,
                        "is_buy_order": False,
                        "issued": (self.now - timedelta(days=1)).isoformat(),
                        "duration": 90,
                    }
                ],
                now=self.now,
                baseline_by_type={34: 5},
            )

        self.assertEqual(sales, 1)
        self.assertEqual(orders, 1)
        sale = EveMarketInferredSale.objects.get()
        self.assertEqual(sale.quantity, 30)
        self.assertEqual(
            sale.reason, EveMarketInferredSale.REASON_PARTIAL_FILL
        )
        order = EveMarketItemOrder.objects.get()
        self.assertEqual(order.quantity, 70)
        self.assertEqual(order.duration_days, 90)
        sync = EveMarketOrderBookSync.objects.get(location=self.location)
        self.assertEqual(sync.last_synced_at, self.now)

    def test_apply_gap_writes_orders_without_sales(self):
        EveMarketItemOrder.objects.create(
            order_id=1,
            item=self.item,
            location=self.location,
            price=Decimal("5.00"),
            quantity=100,
            is_buy_order=False,
        )
        EveMarketOrderBookSync.objects.create(
            location=self.location,
            last_synced_at=self.now - timedelta(hours=2),
        )

        sales, orders = apply_order_book_snapshot(
            self.location,
            [
                {
                    "order_id": 2,
                    "type_id": 34,
                    "price": 5.0,
                    "volume_remain": 40,
                    "is_buy_order": False,
                }
            ],
            now=self.now,
            baseline_by_type={34: 5},
        )

        self.assertEqual(sales, 0)
        self.assertEqual(orders, 1)
        self.assertEqual(EveMarketInferredSale.objects.count(), 0)
        self.assertEqual(EveMarketItemOrder.objects.get().order_id, 2)
