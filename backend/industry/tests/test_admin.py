"""Tests for industry admin customizations."""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.test import Client, RequestFactory
from django.urls import reverse
from django.utils import timezone

from app.test import TestCase
from eveonline.models import EveCharacter
from eveuniverse.models import EveCategory, EveGroup, EveType

from industry.admin import _apply_industry_app_list
from industry.admin_views import (
    industry_order_hub_view,
    industry_orders_home_view,
)
from industry.models import IndustryOrderItem, IndustryOrderItemAssignment
from industry.test_utils import create_industry_order


class IndustryAdminCustomizationsTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.client = Client()
        user_model = get_user_model()
        self.staff = user_model.objects.create_user(
            username="industry-orders-viewer",
            password="test-pass",
            is_staff=True,
            is_superuser=False,
        )
        self.view_perm = Permission.objects.get(
            codename="view_industryorder",
            content_type=ContentType.objects.get(
                app_label="industry", model="industryorder"
            ),
        )
        self.character = EveCharacter.objects.create(
            character_id=777001,
            character_name="Industry Admin Char",
            user=self.user,
        )
        eve_category, _ = EveCategory.objects.get_or_create(
            id=2, defaults={"name": "Admin Category", "published": True}
        )
        eve_group, _ = EveGroup.objects.get_or_create(
            id=2,
            defaults={
                "name": "Admin Group",
                "published": True,
                "eve_category": eve_category,
            },
        )
        self.eve_type = EveType.objects.create(
            id=777201,
            name="Admin Mineral",
            published=True,
            eve_group=eve_group,
        )
        self.order = create_industry_order(
            needed_by=(timezone.now() + timedelta(days=7)).date(),
            character=self.character,
        )
        self.order_item = IndustryOrderItem.objects.create(
            order=self.order,
            eve_type=self.eve_type,
            quantity=3,
        )
        IndustryOrderItemAssignment.objects.create(
            order_item=self.order_item,
            character=self.character,
            quantity=1,
        )

    def test_home_view_requires_permission(self):
        request = self.factory.get(reverse("admin:industry_orders_home"))
        request.user = self.staff
        with self.assertRaises(PermissionDenied):
            industry_orders_home_view(request)

        self.staff.user_permissions.add(self.view_perm)
        user_model = get_user_model()
        self.staff = user_model.objects.get(pk=self.staff.pk)
        request.user = self.staff
        response = industry_orders_home_view(request)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, "Industry orders")
        self.assertContains(response, self.character.character_name)
        self.assertContains(response, "Open hub")

    def test_order_hub_view_shows_sections(self):
        self.staff.user_permissions.add(self.view_perm)
        user_model = get_user_model()
        self.staff = user_model.objects.get(pk=self.staff.pk)
        request = self.factory.get(
            reverse("admin:industry_order_hub", args=[self.order.pk])
        )
        request.user = self.staff
        response = industry_order_hub_view(request, self.order.pk)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, "Order items")
        self.assertContains(response, "Assignments")
        self.assertContains(response, "Edit order")
        self.assertContains(response, "Refresh order breakdown")

    @patch("industry.admin.refresh_order_profit_breakdown")
    def test_refresh_profit_breakdown_admin_view(self, mock_refresh):
        change_perm = Permission.objects.get(
            codename="change_industryorder",
            content_type=ContentType.objects.get(
                app_label="industry", model="industryorder"
            ),
        )
        self.staff.user_permissions.add(self.view_perm, change_perm)
        user_model = get_user_model()
        self.staff = user_model.objects.get(pk=self.staff.pk)
        self.client.force_login(self.staff)
        url = reverse(
            "admin:industry_industryorder_refresh_profit_breakdown",
            args=[self.order.pk],
        )
        get_response = self.client.get(url)
        self.assertEqual(get_response.status_code, 302)
        mock_refresh.assert_not_called()

        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        mock_refresh.assert_called_once()
        self.assertEqual(mock_refresh.call_args.args[0].pk, self.order.pk)

    def test_apply_industry_app_list_hides_nested_models(self):
        self.staff.user_permissions.add(self.view_perm)
        user_model = get_user_model()
        self.staff = user_model.objects.get(pk=self.staff.pk)
        request = self.factory.get("/admin/")
        request.user = self.staff
        app_list = [
            {
                "name": "Supply",
                "app_label": "industry",
                "models": [
                    {
                        "name": "Industry orders",
                        "object_name": "industryorder",
                        "admin_url": "/admin/industry/industryorder/",
                    },
                    {
                        "name": "Freight routes",
                        "object_name": "evefreightroute",
                        "admin_url": "/admin/freight/evefreightroute/",
                    },
                ],
            }
        ]
        result = _apply_industry_app_list(app_list, request)
        supply_app = result[0]
        industry_links = [
            model
            for model in supply_app["models"]
            if model.get("admin_url", "").startswith("/admin/industry/")
        ]
        self.assertEqual(len(industry_links), 1)
        self.assertEqual(industry_links[0]["name"].lower(), "industry orders")
        self.assertEqual(
            industry_links[0]["admin_url"], "/admin/industry/orders/"
        )
        self.assertTrue(
            any(
                model["admin_url"] == "/admin/freight/evefreightroute/"
                for model in supply_app["models"]
            )
        )

    def test_get_app_list_with_app_label(self):
        """app_index passes app_label; patched get_app_list must accept it."""
        user_model = get_user_model()
        user = user_model.objects.create_superuser(
            username="admin_app_list",
            email="admin@example.com",
            password="password",
        )
        # pylint: disable=import-outside-toplevel
        from django.contrib import admin

        request = self.factory.get("/admin/auth/")
        request.user = user
        app_list = admin.site.get_app_list(request, app_label="auth")
        self.assertIsInstance(app_list, list)
