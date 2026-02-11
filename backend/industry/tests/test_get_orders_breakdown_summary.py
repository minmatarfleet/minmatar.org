"""Tests for industry summary endpoints (nested, flat, janice)."""

from datetime import timedelta
from unittest.mock import patch

from django.test import Client
from django.utils import timezone

from eveonline.models import EveCharacter
from eveuniverse.models import EveCategory, EveGroup, EveType

from app.test import TestCase as AppTestCase
from industry.models import IndustryOrder, IndustryOrderItem


class GetOrdersBreakdownSummaryTestCase(AppTestCase):
    """Tests for GET /summary/nested, /summary/flat, /summary/janice."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.eve_category, _ = EveCategory.objects.get_or_create(
            id=1, defaults={"name": "Test Category", "published": True}
        )
        cls.eve_group, _ = EveGroup.objects.get_or_create(
            id=1,
            defaults={
                "name": "Test Group",
                "published": True,
                "eve_category": cls.eve_category,
            },
        )

    def setUp(self):
        super().setUp()
        self.character = EveCharacter.objects.get_or_create(
            character_id=999001,
            defaults={"character_name": "Test Char", "user": self.user},
        )[0]

    def test_nested_returns_200_empty_when_no_orders(self):
        client = Client()
        response = client.get("/api/industry/summary/nested")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"roots": []})

    def test_nested_returns_aggregated_breakdown(self):
        eve_type = EveType.objects.create(
            id=999201,
            name="Test Mineral",
            published=True,
            eve_group=self.eve_group,
        )
        needed_by = (timezone.now() + timedelta(days=7)).date()
        order = IndustryOrder.objects.create(
            needed_by=needed_by,
            character=self.character,
        )
        IndustryOrderItem.objects.create(
            order=order, eve_type=eve_type, quantity=5
        )
        client = Client()
        response = client.get("/api/industry/summary/nested")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["roots"]), 1)
        root = data["roots"][0]
        self.assertEqual(root["type_id"], 999201)
        self.assertEqual(root["name"], "Test Mineral")
        self.assertEqual(root["quantity"], 5)
        self.assertIn("children", root)
        self.assertIn("source", root)
        self.assertIn("depth", root)

    def test_flat_returns_200_empty_when_no_orders(self):
        client = Client()
        response = client.get("/api/industry/summary/flat")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"items": []})

    def test_flat_returns_aggregated_items(self):
        eve_type = EveType.objects.create(
            id=999201,
            name="Test Mineral",
            published=True,
            eve_group=self.eve_group,
        )
        needed_by = (timezone.now() + timedelta(days=7)).date()
        order = IndustryOrder.objects.create(
            needed_by=needed_by,
            character=self.character,
        )
        IndustryOrderItem.objects.create(
            order=order, eve_type=eve_type, quantity=5
        )
        client = Client()
        response = client.get("/api/industry/summary/flat")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["type_id"], 999201)
        self.assertEqual(data["items"][0]["name"], "Test Mineral")
        self.assertEqual(data["items"][0]["quantity"], 5)

    def test_janice_returns_link_when_no_orders(self):
        client = Client()
        response = client.get("/api/industry/summary/janice")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("janice_link", data)
        self.assertIn("janice.e-351.com", data["janice_link"])

    @patch(
        "industry.endpoints.get_orders_breakdown_summary_janice.requests.post"
    )
    def test_janice_returns_link_after_submit(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = []
        mock_post.return_value.raise_for_status = lambda: None
        eve_type = EveType.objects.create(
            id=999201,
            name="Test Mineral",
            published=True,
            eve_group=self.eve_group,
        )
        needed_by = (timezone.now() + timedelta(days=7)).date()
        order = IndustryOrder.objects.create(
            needed_by=needed_by,
            character=self.character,
        )
        IndustryOrderItem.objects.create(
            order=order, eve_type=eve_type, quantity=5
        )
        client = Client()
        response = client.get("/api/industry/summary/janice")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("janice_link", data)
        self.assertIn("janice.e-351.com", data["janice_link"])

    def test_tsv_returns_empty_with_header_when_no_orders(self):
        client = Client()
        response = client.get("/api/industry/summary/tsv")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "text/tab-separated-values; charset=utf-8",
        )
        self.assertEqual(response.content.decode(), "name\tquantity\n")

    def test_tsv_returns_rows_for_copy_paste(self):
        eve_type = EveType.objects.create(
            id=999201,
            name="Test Mineral",
            published=True,
            eve_group=self.eve_group,
        )
        needed_by = (timezone.now() + timedelta(days=7)).date()
        order = IndustryOrder.objects.create(
            needed_by=needed_by,
            character=self.character,
        )
        IndustryOrderItem.objects.create(
            order=order, eve_type=eve_type, quantity=5
        )
        client = Client()
        response = client.get("/api/industry/summary/tsv")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "text/tab-separated-values; charset=utf-8",
        )
        self.assertEqual(
            response.content.decode(), "name\tquantity\nTest Mineral\t5\n"
        )
