"""Tests for market.helpers.pricing.get_prices_by_type_id."""

from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone
from eveuniverse.models import EveCategory, EveGroup, EveMarketPrice, EveType

from app.test import TestCase
from eveonline.models import EveLocation
from market.helpers.pricing import (
    get_history_averages_by_type_id,
    get_prices_by_type_id,
)
from market.models.history import EveMarketItemHistory


def _ensure_type(*, type_id: int, name: str) -> EveType:
    category, _ = EveCategory.objects.get_or_create(
        id=9100,
        defaults={"name": "Material", "published": True},
    )
    group, _ = EveGroup.objects.get_or_create(
        id=9100,
        defaults={
            "name": "Mineral",
            "published": True,
            "eve_category": category,
        },
    )
    eve_type, _ = EveType.objects.get_or_create(
        id=type_id,
        defaults={
            "name": name,
            "published": True,
            "eve_group": group,
        },
    )
    return eve_type


class GetPricesByTypeIdTestCase(TestCase):
    def setUp(self):
        EveLocation.objects.create(
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
        self.trit = _ensure_type(type_id=34, name="Tritanium")
        self.pyx = _ensure_type(type_id=35, name="Pyerite")
        self.today = timezone.now().date()

    def test_empty_input(self):
        self.assertEqual(get_prices_by_type_id([]), {})

    def test_picks_latest_history_row_only(self):
        EveMarketItemHistory.objects.create(
            region_id=10000002,
            item=self.trit,
            date=self.today - timedelta(days=2),
            average=Decimal("2.00"),
            highest=Decimal("2.10"),
            lowest=Decimal("1.90"),
            volume=100,
        )
        EveMarketItemHistory.objects.create(
            region_id=10000002,
            item=self.trit,
            date=self.today,
            average=Decimal("5.00"),
            highest=Decimal("5.10"),
            lowest=Decimal("4.90"),
            volume=200,
        )
        prices = get_prices_by_type_id([self.trit.id])
        self.assertEqual(prices[self.trit.id], 5)

    def test_falls_back_to_eve_market_price(self):
        EveMarketPrice.objects.create(
            eve_type=self.pyx,
            average_price=Decimal("12.50"),
            adjusted_price=Decimal("12.00"),
        )
        prices = get_prices_by_type_id([self.pyx.id])
        self.assertEqual(prices[self.pyx.id], 12)

    def test_preserves_fractional_averages_via_history_helper(self):
        EveMarketItemHistory.objects.create(
            region_id=10000002,
            item=self.trit,
            date=self.today,
            average=Decimal("3.93"),
            highest=Decimal("3.94"),
            lowest=Decimal("3.89"),
            volume=100,
        )
        averages = get_history_averages_by_type_id([self.trit.id])
        self.assertEqual(averages[self.trit.id], Decimal("3.93"))
        self.assertEqual(
            get_prices_by_type_id([self.trit.id])[self.trit.id], 3
        )

    def test_ignores_other_region_history(self):
        EveMarketItemHistory.objects.create(
            region_id=10000043,
            item=self.trit,
            date=self.today,
            average=Decimal("99.00"),
            highest=Decimal("100.00"),
            lowest=Decimal("98.00"),
            volume=10,
        )
        EveMarketItemHistory.objects.create(
            region_id=10000002,
            item=self.trit,
            date=date(2026, 1, 1),
            average=Decimal("3.00"),
            highest=Decimal("3.10"),
            lowest=Decimal("2.90"),
            volume=10,
        )
        prices = get_prices_by_type_id([self.trit.id])
        self.assertEqual(prices[self.trit.id], 3)
