"""
Shared baseline live-book reader (market.helpers.pricing.baseline_book).

The ``_old_*`` functions are verbatim copies of the private readers that
buyback, industry and the sell-orders endpoint each kept before they were
moved onto ``baseline_book``. The parity tests pin that every wrapper still
returns exactly what its old reader did, for rows missing sell/buy/split in
every combination, with a second location's rows that must be ignored.
"""

from datetime import timedelta
from decimal import Decimal
from itertools import product
from unittest.mock import patch

from django.utils import timezone
from eveuniverse.models import EveCategory, EveGroup, EveType

from app.test import TestCase
from buyback.helpers.pricing import _live_jita_buys_by_type_id
from eveonline.models import EveLocation
from industry.helpers.cost_breakdown import jita_sell_prices_by_type_id
from industry.helpers.lp_store_economics import _baseline_location_prices
from market.endpoints.get_sell_orders import _get_baseline_location_prices
from market.helpers.pricing import (
    BaselineBookRow,
    baseline_book,
    baseline_location,
    baseline_region_id,
    enqueue_history_for_types,
    get_prices_by_type_id,
)
from market.models import EveMarketItemLocationPrice
from market.models.history import EveMarketItemHistory

# --- Old private readers, copied verbatim for parity -----------------------


def _old_buyback_live_jita_buys(type_ids):
    if not type_ids:
        return {}
    unique_ids = list({int(tid) for tid in type_ids})
    baseline = EveLocation.objects.filter(price_baseline=True).first()
    if baseline is None:
        return {}
    prices = {}
    rows = EveMarketItemLocationPrice.objects.filter(
        location=baseline,
        item_id__in=unique_ids,
    ).values_list("item_id", "buy_price", "split_price")
    for type_id, buy_price, split_price in rows:
        if buy_price is not None:
            prices[int(type_id)] = Decimal(str(buy_price))
        elif split_price is not None:
            prices[int(type_id)] = Decimal(str(split_price))
    return prices


def _old_sell_pricing_live_rows(type_ids):
    if not type_ids:
        return {}
    baseline = EveLocation.objects.filter(price_baseline=True).first()
    if baseline is None:
        return {}
    rows = EveMarketItemLocationPrice.objects.filter(
        location=baseline,
        item_id__in=type_ids,
    ).values_list("item_id", "buy_price", "sell_price", "split_price")
    return {
        int(type_id): (buy_price, sell_price, split_price)
        for type_id, buy_price, sell_price, split_price in rows
    }


def _old_jita_sell_prices_by_type_id(type_ids):
    unique = list({int(tid) for tid in type_ids if tid})
    if not unique:
        return {}
    prices = {}
    baseline = EveLocation.objects.filter(price_baseline=True).first()
    if baseline is not None:
        for tid, sell in EveMarketItemLocationPrice.objects.filter(
            location=baseline, item_id__in=unique
        ).values_list("item_id", "sell_price"):
            if sell is not None:
                prices[int(tid)] = int(sell)
    missing = [tid for tid in unique if tid not in prices]
    if missing:
        prices.update(get_prices_by_type_id(missing))
    return prices


def _old_lp_baseline_location_prices(type_ids):
    unique = list({int(t) for t in type_ids})
    if not unique:
        return {}
    baseline = EveLocation.objects.filter(price_baseline=True).first()
    if baseline is None:
        return {}
    out = {}
    for row in EveMarketItemLocationPrice.objects.filter(
        location=baseline, item_id__in=unique
    ).values_list("item_id", "sell_price", "buy_price"):
        item_id, sell, buy = row
        out[int(item_id)] = (
            int(sell) if sell is not None else None,
            int(buy) if buy is not None else None,
        )
    return out


def _old_sell_orders_baseline_prices():
    baseline = EveLocation.objects.filter(price_baseline=True).first()
    if not baseline:
        return {}
    rows = (
        EveMarketItemLocationPrice.objects.filter(location=baseline)
        .select_related("item")
        .values_list("item__name", "sell_price", "buy_price", "split_price")
    )
    return {
        name: (
            float(sell) if sell is not None else None,
            float(buy) if buy is not None else None,
            float(split) if split is not None else None,
        )
        for name, sell, buy, split in rows
    }


def _old_loyalty_region_id():
    baseline = EveLocation.objects.filter(price_baseline=True).first()
    return (
        baseline.region_id
        if baseline and baseline.region_id
        else 10000002  # JITA_REGION_ID
    )


# --- Fixtures --------------------------------------------------------------


def _group():
    category, _ = EveCategory.objects.get_or_create(
        id=9300, defaults={"name": "Material", "published": True}
    )
    group, _ = EveGroup.objects.get_or_create(
        id=9300,
        defaults={
            "name": "Mineral",
            "published": True,
            "eve_category": category,
        },
    )
    return group


def _location(location_id, *, baseline, region_id=10000002):
    return EveLocation.objects.create(
        location_id=location_id,
        location_name=f"Location {location_id}",
        solar_system_id=30000142,
        solar_system_name="Jita",
        short_name=f"L{location_id}",
        region_id=region_id,
        price_baseline=baseline,
        prices_active=True,
        market_active=False,
    )


class BaselineBookParityTestCase(TestCase):
    """
    Every combination of buy/split present or missing (``sell_price`` is
    NOT NULL on the model), plus a type with no baseline row at all.
    """

    def setUp(self):
        self.baseline = _location(60003760, baseline=True)
        self.other = _location(60008494, baseline=False, region_id=10000043)
        group = _group()
        self.type_ids = []
        values = (Decimal("101.75"), Decimal("88.40"), Decimal("95.08"))
        combos = [(True, buy, split) for buy, split in product((1, 0), (1, 0))]
        for index, present in enumerate(combos):
            type_id = 950000 + index
            eve_type = EveType.objects.create(
                id=type_id,
                name=f"Parity Type {index}",
                published=True,
                eve_group=group,
            )
            self.type_ids.append(type_id)
            sell, buy, split = (
                value if keep else None for value, keep in zip(values, present)
            )
            EveMarketItemLocationPrice.objects.create(
                location=self.baseline,
                item=eve_type,
                sell_price=sell,
                buy_price=buy,
                split_price=split,
            )
            # Another hub's book must never leak into the baseline reader.
            EveMarketItemLocationPrice.objects.create(
                location=self.other,
                item=eve_type,
                sell_price=Decimal("1.00"),
                buy_price=Decimal("1.00"),
                split_price=Decimal("1.00"),
            )
        # A type with no baseline row at all, and history for the fallback.
        self.no_row = EveType.objects.create(
            id=950100, name="Parity No Row", published=True, eve_group=group
        )
        self.type_ids.append(self.no_row.id)
        EveMarketItemHistory.objects.create(
            region_id=10000002,
            item=self.no_row,
            date=timezone.now().date(),
            average=Decimal("12.34"),
            highest=Decimal("13"),
            lowest=Decimal("12"),
            volume=10,
        )

    def test_buyback_live_buys_match_old_reader(self):
        self.assertEqual(
            _live_jita_buys_by_type_id(self.type_ids),
            _old_buyback_live_jita_buys(self.type_ids),
        )

    def test_buyback_sell_rows_match_old_reader(self):
        old = _old_sell_pricing_live_rows(self.type_ids)
        new = {
            tid: (row.buy, row.sell, row.split)
            for tid, row in baseline_book(self.type_ids).items()
        }
        self.assertEqual(new, old)

    def test_industry_jita_sell_matches_old_reader(self):
        self.assertEqual(
            jita_sell_prices_by_type_id(self.type_ids),
            _old_jita_sell_prices_by_type_id(self.type_ids),
        )

    def test_lp_baseline_prices_match_old_reader(self):
        self.assertEqual(
            _baseline_location_prices(self.type_ids),
            _old_lp_baseline_location_prices(self.type_ids),
        )

    def test_sell_orders_baseline_prices_match_old_reader(self):
        names = dict(
            EveType.objects.filter(id__in=self.type_ids).values_list(
                "name", "id"
            )
        )
        type_info = {
            name: (type_id, None, "", None, "")
            for name, type_id in names.items()
        }
        type_info["Unknown Item"] = (None, None, "", None, "")
        old = _old_sell_orders_baseline_prices()
        self.assertEqual(
            _get_baseline_location_prices(type_info),
            {name: old[name] for name in type_info if name in old},
        )

    def test_region_matches_old_loyalty_lookup(self):
        self.assertEqual(baseline_region_id(), _old_loyalty_region_id())

    def test_no_baseline_location(self):
        EveLocation.objects.filter(price_baseline=True).update(
            price_baseline=False
        )
        self.assertIsNone(baseline_location())
        self.assertEqual(baseline_book(self.type_ids), {})
        self.assertEqual(
            _live_jita_buys_by_type_id(self.type_ids),
            _old_buyback_live_jita_buys(self.type_ids),
        )
        self.assertEqual(
            _baseline_location_prices(self.type_ids),
            _old_lp_baseline_location_prices(self.type_ids),
        )
        self.assertEqual(baseline_region_id(), _old_loyalty_region_id())

    def test_book_rows_are_decimals(self):
        row = baseline_book([self.type_ids[0]])[self.type_ids[0]]
        self.assertEqual(
            row,
            BaselineBookRow(
                sell=Decimal("101.75"),
                buy=Decimal("88.40"),
                split=Decimal("95.08"),
            ),
        )

    def test_empty_input(self):
        self.assertEqual(baseline_book([]), {})
        self.assertEqual(baseline_book([None, 0]), {})


class EnqueueHistoryForTypesTestCase(TestCase):
    def setUp(self):
        _location(60003760, baseline=True)
        group = _group()
        self.fresh = EveType.objects.create(
            id=950200, name="Fresh", published=True, eve_group=group
        )
        self.stale = EveType.objects.create(
            id=950201, name="Stale", published=True, eve_group=group
        )
        self.today = timezone.now().date()
        for eve_type, age in ((self.fresh, 0), (self.stale, 10)):
            EveMarketItemHistory.objects.create(
                region_id=10000002,
                item=eve_type,
                date=self.today - timedelta(days=age),
                average=Decimal("1"),
                highest=Decimal("1"),
                lowest=Decimal("1"),
                volume=1,
            )

    @patch("market.tasks.fetch_market_item_history_for_type.apply_async")
    def test_queues_only_types_without_history(self, apply_async):
        queued = enqueue_history_for_types(
            [self.fresh.id, self.stale.id, 950299]
        )
        self.assertEqual(queued, [950299])
        apply_async.assert_called_once_with(args=[950299])

    @patch("market.tasks.fetch_market_item_history_for_type.apply_async")
    def test_stale_before_also_queues_old_history(self, apply_async):
        queued = enqueue_history_for_types(
            [self.fresh.id, self.stale.id],
            stale_before=self.today - timedelta(days=2),
        )
        self.assertEqual(queued, [self.stale.id])
        self.assertEqual(apply_async.call_count, 1)
