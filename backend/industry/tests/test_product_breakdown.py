"""Tests for industry products endpoints: GET list, GET breakdown by ID."""

from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import Client

from eveuniverse.models import EveCategory, EveGroup, EveType

from app.test import TestCase as AppTestCase
from industry.models import IndustryProduct, Strategy


def _mock_breakdown_for_product(
    eve_type, quantity=1, max_depth=None, store=True
):
    """Minimal nested breakdown tree."""
    return {
        "name": eve_type.name,
        "type_id": eve_type.id,
        "quantity": quantity,
        "source": "raw",
        "depth": 0,
        "children": [],
    }


class ProductBreakdownTestCase(AppTestCase):
    """Tests for industry product breakdown by ID."""

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
        self.client = Client()
        self.eve_type = EveType.objects.create(
            id=999301,
            name="Test Product Type",
            published=True,
            eve_group=self.eve_group,
        )
        self.product = IndustryProduct.objects.create(
            eve_type=self.eve_type,
            strategy="imported",
            breakdown={
                "name": self.eve_type.name,
                "type_id": self.eve_type.id,
                "quantity": 1,
                "source": "raw",
                "depth": 0,
                "children": [],
            },
        )

    def _auth_headers(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

    @patch(
        "industry.helpers.type_breakdown.get_breakdown_for_industry_product"
    )
    def test_get_product_breakdown_returns_200_with_tree(self, mock_breakdown):
        mock_breakdown.side_effect = _mock_breakdown_for_product
        response = self.client.get(
            f"/api/industry/products/{self.product.pk}/breakdown",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], self.eve_type.name)
        self.assertEqual(data["type_id"], self.eve_type.id)
        self.assertIn("industry_product_id", data)
        self.assertEqual(data["industry_product_id"], self.product.pk)

    def test_get_product_breakdown_returns_404_when_not_found(self):
        response = self.client.get(
            "/api/industry/products/999999/breakdown",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 404)

    def test_get_products_returns_200_with_list(self):
        response = self.client.get(
            "/api/industry/products",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], self.product.pk)
        self.assertEqual(data[0]["type_id"], self.eve_type.id)
        self.assertEqual(data[0]["name"], self.eve_type.name)
        self.assertEqual(data[0]["strategy"], "imported")
        self.assertIn("volume", data[0])
        self.assertIn("blueprint_or_reaction_type_id", data[0])
        self.assertIn("supplied_for", data[0])
        self.assertIn("supplies", data[0])
        self.assertEqual(data[0]["supplied_for"], [])
        self.assertEqual(data[0]["supplies"], [])
        self.assertIn("character_producers", data[0])
        self.assertIn("corporation_producers", data[0])
        self.assertEqual(data[0]["character_producers"], [])
        self.assertEqual(data[0]["corporation_producers"], [])

    def test_get_product_returns_200_with_detail(self):
        """GET /products/{id} returns full detail including supplied_for and supplies."""
        response = self.client.get(
            f"/api/industry/products/{self.product.pk}",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], self.product.pk)
        self.assertEqual(data["type_id"], self.eve_type.id)
        self.assertEqual(data["name"], self.eve_type.name)
        self.assertEqual(data["strategy"], "imported")
        self.assertIn("volume", data)
        self.assertIn("blueprint_or_reaction_type_id", data)
        self.assertEqual(data["supplied_for"], [])
        self.assertEqual(data["supplies"], [])
        self.assertIn("character_producers", data)
        self.assertIn("corporation_producers", data)
        self.assertEqual(data["character_producers"], [])
        self.assertEqual(data["corporation_producers"], [])

    def test_get_product_returns_404_when_not_found(self):
        response = self.client.get(
            "/api/industry/products/999999",
            **self._auth_headers(),
        )
        self.assertEqual(response.status_code, 404)

    def test_cannot_mark_as_produced_without_blueprint(self):
        """Strategy=produced is invalid when the type has no blueprint or reaction."""
        product = IndustryProduct(
            eve_type=self.eve_type,
            strategy=Strategy.PRODUCED,
        )
        with self.assertRaises(ValidationError) as cm:
            product.full_clean()
        self.assertIn("strategy", cm.exception.message_dict)
