from datetime import datetime, timezone as dt_timezone
from decimal import Decimal

from django.core.cache import cache
from django.test import Client

from app.test import TestCase
from eveonline.models import EveLocation
from market.helpers.inferred_sales_monthly import (
    build_monthly_response,
    month_bounds,
)
from market.models import EveMarketInferredSale
from market.tests.test_fitting_expectations import _make_typed_eve_type

BASE_URL = "/api/market"
AMAMAKE = 1022167642188


def _utc(*args):
    return datetime(*args, tzinfo=dt_timezone.utc)


class InferredSalesMonthlyTestCase(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.client = Client()
        self.location = EveLocation.objects.create(
            location_id=AMAMAKE,
            location_name="Amamake - 5 times nearly AT winners",
            short_name="Amamake",
            solar_system_id=30002537,
            solar_system_name="Amamake",
            market_active=True,
        )
        self.rifter = _make_typed_eve_type(587, "Rifter", 6, "Ship")
        self.paste = _make_typed_eve_type(
            28668, "Nanite Repair Paste", 8, "Charge"
        )

    def _sale(self, item, quantity, price, at, location=None):
        return EveMarketInferredSale.objects.create(
            location=location or self.location,
            item=item,
            quantity=quantity,
            price=Decimal(str(price)),
            inferred_at=at,
            reason=EveMarketInferredSale.REASON_PARTIAL_FILL,
        )

    def test_month_bounds(self):
        start, end = month_bounds(2026, 8)
        self.assertEqual(start, _utc(2026, 8, 1))
        self.assertEqual(end, _utc(2026, 9, 1))
        start, end = month_bounds(2026, 12)
        self.assertEqual(end, _utc(2027, 1, 1))
        with self.assertRaises(ValueError):
            month_bounds(2026, 13)

    def test_monthly_totals_days_and_types(self):
        # Two August fills for the Rifter, one for paste, one July row
        # and one September row that must both be excluded.
        self._sale(self.rifter, 2, 1_000_000, _utc(2026, 8, 3, 12))
        self._sale(self.rifter, 1, 1_100_000, _utc(2026, 8, 20, 9))
        self._sale(self.paste, 500, 28_000, _utc(2026, 8, 3, 15))
        self._sale(self.rifter, 9, 1_000_000, _utc(2026, 7, 31, 23, 59))
        self._sale(self.rifter, 9, 1_000_000, _utc(2026, 9, 1, 0, 0))

        payload = build_monthly_response(AMAMAKE, 2026, 8)

        self.assertEqual(payload["totals"]["fills"], 3)
        self.assertEqual(payload["totals"]["units"], 503)
        self.assertAlmostEqual(payload["totals"]["isk"], 17_100_000.0)
        self.assertEqual(payload["totals"]["types"], 2)

        self.assertEqual(
            [(d["date"], d["fills"], d["units"]) for d in payload["days"]],
            [("2026-08-03", 2, 502), ("2026-08-20", 1, 1)],
        )
        self.assertAlmostEqual(payload["days"][0]["isk"], 16_000_000.0)

        by_type = payload["by_type"]
        self.assertEqual([t["type_id"] for t in by_type], [28668, 587])
        self.assertEqual(by_type[0]["category"], "Charge")
        self.assertEqual(by_type[1]["name"], "Rifter")
        self.assertEqual(by_type[1]["fills"], 2)
        self.assertEqual(by_type[1]["units"], 3)
        self.assertAlmostEqual(by_type[1]["isk"], 3_100_000.0)

    def test_other_location_excluded(self):
        other = EveLocation.objects.create(
            location_id=60003760,
            location_name="Jita IV - Moon 4",
            short_name="Jita",
            solar_system_id=30000142,
            solar_system_name="Jita",
            market_active=True,
        )
        self._sale(self.rifter, 5, 1_000_000, _utc(2026, 8, 3), location=other)
        payload = build_monthly_response(AMAMAKE, 2026, 8)
        self.assertEqual(payload["totals"]["fills"], 0)
        self.assertEqual(payload["days"], [])
        self.assertEqual(payload["by_type"], [])

    def test_endpoint(self):
        self._sale(self.rifter, 2, 1_000_000, _utc(2026, 8, 3, 12))
        response = self.client.get(
            f"{BASE_URL}/inferred-sales/monthly",
            {"location_id": AMAMAKE, "year": 2026, "month": 8},
        )
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(body["month"], 8)
        self.assertEqual(body["totals"]["units"], 2)
        self.assertEqual(body["by_type"][0]["name"], "Rifter")

    def test_endpoint_rejects_bad_month(self):
        response = self.client.get(
            f"{BASE_URL}/inferred-sales/monthly",
            {"location_id": AMAMAKE, "year": 2026, "month": 13},
        )
        self.assertEqual(400, response.status_code)
