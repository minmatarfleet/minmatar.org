from datetime import datetime, timezone as dt_timezone
from decimal import Decimal

import jwt
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client

from app.test import TestCase
from eveonline.models import EveLocation
from market.helpers.inferred_sales_monthly import (
    build_monthly_response,
    month_bounds,
)
from market.helpers.inferred_sales_monthly_volume import (
    PAGE_SIZE,
    build_volume_page,
    class_slug,
)
from market.models import EveMarketInferredSale
from market.tests.test_fitting_expectations import _make_typed_eve_type

BASE_URL = "/api/market"
AMAMAKE = 1022167642188


def _utc(*args):
    return datetime(*args, tzinfo=dt_timezone.utc)


def _token_for(user: User) -> str:
    return jwt.encode(
        {"user_id": user.id}, settings.SECRET_KEY, algorithm="HS256"
    )


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
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

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
            [t["type_id"] for t in payload["by_type"]], [28668, 587]
        )

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

    def test_endpoint_requires_auth(self):
        self._sale(self.rifter, 2, 1_000_000, _utc(2026, 8, 3, 12))
        response = self.client.get(
            f"{BASE_URL}/inferred-sales/monthly",
            {"location_id": AMAMAKE, "year": 2026, "month": 8},
        )
        self.assertEqual(401, response.status_code)

    def test_endpoint_strips_by_type_for_non_staff(self):
        self._sale(self.rifter, 2, 1_000_000, _utc(2026, 8, 3, 12))
        response = self.client.get(
            f"{BASE_URL}/inferred-sales/monthly",
            {
                "location_id": AMAMAKE,
                "year": 2026,
                "month": 8,
                "include_types": "true",
            },
            **self.auth,
        )
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(body["totals"]["units"], 2)
        self.assertEqual(body["by_type"], [])

    def test_endpoint_staff_include_types(self):
        self.user.is_staff = True
        self.user.save()
        self._sale(self.rifter, 2, 1_000_000, _utc(2026, 8, 3, 12))
        response = self.client.get(
            f"{BASE_URL}/inferred-sales/monthly",
            {
                "location_id": AMAMAKE,
                "year": 2026,
                "month": 8,
                "include_types": "true",
            },
            **self.auth,
        )
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(body["by_type"][0]["name"], "Rifter")

    def test_endpoint_rejects_bad_month(self):
        response = self.client.get(
            f"{BASE_URL}/inferred-sales/monthly",
            {"location_id": AMAMAKE, "year": 2026, "month": 13},
            **self.auth,
        )
        self.assertEqual(400, response.status_code)


class InferredSalesMonthlyVolumeTestCase(TestCase):
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
        self.types = []
        for i in range(PAGE_SIZE + 5):
            item = _make_typed_eve_type(
                10_000 + i, f"Hull {i}", 6, "Ship", group_id=600 + i
            )
            self.types.append(item)
            EveMarketInferredSale.objects.create(
                location=self.location,
                item=item,
                quantity=1,
                price=Decimal(str(1_000_000 * (PAGE_SIZE + 5 - i))),
                inferred_at=_utc(2026, 8, 3, 12),
                reason=EveMarketInferredSale.REASON_PARTIAL_FILL,
            )
        self.skin = _make_typed_eve_type(
            99901, "Rifter Firewatch SKIN", 6, "Ship", group_id=999
        )
        EveMarketInferredSale.objects.create(
            location=self.location,
            item=self.skin,
            quantity=1,
            price=Decimal("50000000"),
            inferred_at=_utc(2026, 8, 3, 12),
            reason=EveMarketInferredSale.REASON_PARTIAL_FILL,
        )
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

    def test_page_slice_and_skin_filter(self):
        page = build_volume_page(AMAMAKE, 2026, 8, page=1, sort="isk")
        self.assertEqual(page["page_size"], PAGE_SIZE)
        self.assertEqual(len(page["rows"]), PAGE_SIZE)
        self.assertEqual(page["total"], PAGE_SIZE + 5)
        self.assertTrue(all("SKIN" not in row["name"] for row in page["rows"]))
        # Highest ISK first
        self.assertEqual(page["rows"][0]["name"], "Hull 0")

    def test_invalid_sort(self):
        with self.assertRaises(ValueError):
            build_volume_page(AMAMAKE, 2026, 8, sort="nope")

    def test_class_slug_collapses_ampersand_spaces(self):
        self.assertEqual(
            class_slug("Materials & commodities"),
            "materials-commodities",
        )
        self.assertEqual(class_slug("PLEX adjacent"), "plex-adjacent")

    def test_endpoint_page_one_anonymous(self):
        response = self.client.get(
            f"{BASE_URL}/inferred-sales/monthly/types",
            {"location_id": AMAMAKE, "year": 2026, "month": 8},
        )
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(len(body["rows"]), PAGE_SIZE)
        self.assertEqual(body["page_size"], PAGE_SIZE)

    def test_endpoint_page_two_anonymous(self):
        response = self.client.get(
            f"{BASE_URL}/inferred-sales/monthly/types",
            {
                "location_id": AMAMAKE,
                "year": 2026,
                "month": 8,
                "page": 2,
            },
        )
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(body["page"], 2)
        self.assertEqual(len(body["rows"]), 5)

    def test_endpoint_search_by_name(self):
        response = self.client.get(
            f"{BASE_URL}/inferred-sales/monthly/types",
            {
                "location_id": AMAMAKE,
                "year": 2026,
                "month": 8,
                "q": "Hull 0",
            },
        )
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(body["q"], "Hull 0")
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["rows"][0]["name"], "Hull 0")

    def test_endpoint_search_no_match(self):
        response = self.client.get(
            f"{BASE_URL}/inferred-sales/monthly/types",
            {
                "location_id": AMAMAKE,
                "year": 2026,
                "month": 8,
                "q": "zzzz-nope",
            },
        )
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(body["total"], 0)
        self.assertEqual(body["rows"], [])

    def test_endpoint_page_two_authed(self):
        response = self.client.get(
            f"{BASE_URL}/inferred-sales/monthly/types",
            {
                "location_id": AMAMAKE,
                "year": 2026,
                "month": 8,
                "page": 2,
            },
            **self.auth,
        )
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(body["page"], 2)
        self.assertEqual(len(body["rows"]), 5)

    def test_endpoint_ignores_client_page_size(self):
        response = self.client.get(
            f"{BASE_URL}/inferred-sales/monthly/types",
            {
                "location_id": AMAMAKE,
                "year": 2026,
                "month": 8,
                "page_size": 3000,
            },
        )
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(body["page_size"], PAGE_SIZE)
        self.assertEqual(len(body["rows"]), PAGE_SIZE)

    def test_endpoint_invalid_sort(self):
        response = self.client.get(
            f"{BASE_URL}/inferred-sales/monthly/types",
            {
                "location_id": AMAMAKE,
                "year": 2026,
                "month": 8,
                "sort": "hack",
            },
        )
        self.assertEqual(400, response.status_code)

    def test_endpoint_anon_budget_asks_login(self):
        # Exhaust the anonymous IP bucket (capacity 8).
        for _ in range(10):
            response = self.client.get(
                f"{BASE_URL}/inferred-sales/monthly/types",
                {"location_id": AMAMAKE, "year": 2026, "month": 8},
            )
        self.assertEqual(401, response.status_code)
        self.assertEqual(response.json()["detail"], "login_required")
        self.assertIn("Retry-After", response.headers)

    def test_endpoint_authed_rate_limit(self):
        # Exhaust the user bucket (capacity 20).
        for _ in range(22):
            response = self.client.get(
                f"{BASE_URL}/inferred-sales/monthly/types",
                {"location_id": AMAMAKE, "year": 2026, "month": 8},
                **self.auth,
            )
        self.assertEqual(429, response.status_code)
        self.assertIn("Retry-After", response.headers)
