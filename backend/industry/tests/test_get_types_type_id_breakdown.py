"""Tests for industry.endpoints.get_types_type_id_breakdown."""

from unittest.mock import patch

from django.test import Client

from eveuniverse.models import EveCategory, EveGroup, EveType

from app.test import TestCase as AppTestCase


class GetTypesTypeIdBreakdownTestCase(AppTestCase):
    """Tests for GET /types/{type_id}/breakdown endpoint."""

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

    @patch("industry.endpoints.get_types_type_id_breakdown.EveType")
    def test_returns_200_with_nested_breakdown(self, mock_eve_type_cls):
        eve_type = EveType.objects.create(
            id=999101,
            name="Test Type",
            published=True,
            eve_group=self.eve_group,
        )
        mock_eve_type_cls.objects.get_or_create_esi.return_value = (
            eve_type,
            False,
        )
        client = Client()
        response = client.get(f"/api/industry/types/{eve_type.id}/breakdown")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "Test Type")
        self.assertEqual(data["type_id"], 999101)
        self.assertEqual(data["quantity"], 1)
        self.assertIn("children", data)

    @patch("industry.endpoints.get_types_type_id_breakdown.EveType")
    def test_quantity_query_param(self, mock_eve_type_cls):
        eve_type = EveType.objects.create(
            id=999102,
            name="Test Type 2",
            published=True,
            eve_group=self.eve_group,
        )
        mock_eve_type_cls.objects.get_or_create_esi.return_value = (
            eve_type,
            False,
        )
        client = Client()
        response = client.get(
            f"/api/industry/types/{eve_type.id}/breakdown?quantity=5"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["quantity"], 5)
