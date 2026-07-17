from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory
from django.urls import reverse

from app.test import TestCase
from help_tickets.admin import _apply_help_tickets_app_list
from help_tickets.admin_views import (
    help_category_hub_view,
    help_tickets_home_view,
)
from help_tickets.models import HelpRequestCategory, HelpTicket


class HelpTicketsAdminCustomizationsTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        user_model = get_user_model()
        self.staff = user_model.objects.create_user(
            username="help-tickets-viewer",
            password="test-pass",
            is_staff=True,
            is_superuser=False,
        )
        self.view_perm = Permission.objects.get(
            codename="view_helprequestcategory",
            content_type=ContentType.objects.get(
                app_label="help_tickets", model="helprequestcategory"
            ),
        )
        self.category = HelpRequestCategory.objects.create(
            title="Contact the freighter team",
            code="supply.freighters",
            section="Supply",
        )
        self.ticket = HelpTicket.objects.create(
            category=self.category,
            opener_discord_id=123456789,
            thread_id=987654321,
            thread_name="help-market-freighters-1",
            body="Need a Jita run",
        )

    def test_home_view_requires_permission(self):
        request = self.factory.get(reverse("admin:help_tickets_home"))
        request.user = self.staff
        with self.assertRaises(PermissionDenied):
            help_tickets_home_view(request)

        self.staff.user_permissions.add(self.view_perm)
        user_model = get_user_model()
        self.staff = user_model.objects.get(pk=self.staff.pk)
        request.user = self.staff
        response = help_tickets_home_view(request)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, "Contact the freighter team")
        self.assertContains(response, "help-market-freighters-1")
        self.assertContains(response, "Discord panel")

    def test_category_hub_view_shows_sections(self):
        self.staff.user_permissions.add(self.view_perm)
        user_model = get_user_model()
        self.staff = user_model.objects.get(pk=self.staff.pk)
        request = self.factory.get(
            reverse("admin:help_tickets_category_hub", args=[self.category.pk])
        )
        request.user = self.staff
        response = help_category_hub_view(request, self.category.pk)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, "Open tickets")
        self.assertContains(response, "Closed tickets")

    def test_apply_help_tickets_app_list_replaces_models(self):
        self.staff.user_permissions.add(self.view_perm)
        user_model = get_user_model()
        self.staff = user_model.objects.get(pk=self.staff.pk)
        request = self.factory.get("/admin/")
        request.user = self.staff
        app_list = [
            {
                "name": "Community",
                "app_label": "groups",
                "models": [
                    {
                        "name": "Help request categories",
                        "object_name": "helprequestcategory",
                        "admin_url": "/admin/help_tickets/helprequestcategory/",
                    },
                    {
                        "name": "Help tickets",
                        "object_name": "helpticket",
                        "admin_url": "/admin/help_tickets/helpticket/",
                    },
                    {
                        "name": "Help ticket panels",
                        "object_name": "helpticketpanel",
                        "admin_url": "/admin/help_tickets/helpticketpanel/",
                    },
                    {
                        "name": "Groups",
                        "object_name": "group",
                        "admin_url": "/admin/groups/group/",
                    },
                ],
            }
        ]
        result = _apply_help_tickets_app_list(app_list, request)
        community_app = result[0]
        help_ticket_links = [
            model
            for model in community_app["models"]
            if model.get("admin_url", "").startswith("/admin/help-tickets/")
            or model.get("admin_url", "").startswith("/admin/help_tickets/")
        ]
        self.assertEqual(len(help_ticket_links), 1)
        self.assertEqual(help_ticket_links[0]["name"].lower(), "help tickets")
        self.assertTrue(
            any(
                model["admin_url"] == "/admin/groups/group/"
                for model in community_app["models"]
            )
        )
