"""Help ticket categories managed from the site."""

import json

from django.contrib.auth.models import Permission, User
from django.test import Client, TestCase

from app.testing import make_token
from help_tickets.models import HelpRequestCategory, HelpTicketPanel
from tribes.models import Tribe, TribeGroup

BASE = "/api/help-tickets/manage"


class HelpSettingsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("owner", password="x")
        self.headers = {
            "HTTP_AUTHORIZATION": f"Bearer {make_token(self.user)}"
        }
        tribe = Tribe.objects.create(name="Pulse", slug="pulse")
        self.group = TribeGroup.objects.create(
            tribe=tribe, name="Technology", code="pulse.technology"
        )
        self.first = HelpRequestCategory.objects.create(
            title="First", code="first", sort_order=10
        )
        self.second = HelpRequestCategory.objects.create(
            title="Second", code="second", sort_order=20
        )

    def grant(self):
        self.user.user_permissions.add(
            Permission.objects.get(
                codename="change_helprequestcategory",
                content_type__app_label="help_tickets",
            )
        )

    def send(self, method, path, data=None):
        return getattr(self.client, method)(
            BASE + path,
            data=json.dumps(data) if data is not None else None,
            content_type="application/json",
            **self.headers,
        )

    def test_everything_needs_the_feature(self):
        for method, path, body in (
            ("get", "/settings", None),
            ("post", "/categories", {"title": "x"}),
            ("patch", f"/categories/{self.first.id}", {"title": "x"}),
            ("post", "/category-order", {"ids": []}),
            ("patch", "/panel", {"channel_id": "1"}),
        ):
            with self.subTest(path=path):
                response = self.send(method, path, body)
                self.assertEqual(403, response.status_code)

    def test_settings_lists_categories_groups_and_panel(self):
        self.grant()
        HelpTicketPanel.objects.create(channel_id=555)
        data = self.send("get", "/settings").json()
        self.assertEqual(
            ["First", "Second"], [c["title"] for c in data["categories"]]
        )
        self.assertEqual("Technology", data["tribe_groups"][0]["name"])
        self.assertEqual("555", data["panel"]["channel_id"])

    def test_create_makes_a_unique_code_and_goes_last(self):
        self.grant()
        response = self.send("post", "/categories", {"title": "First"})
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual("first-2", body["code"])
        self.assertEqual(30, body["sort_order"])
        self.assertEqual(
            400, self.send("post", "/categories", {"title": " "}).status_code
        )

    def test_create_linked_to_a_group_takes_its_code_once(self):
        self.grant()
        response = self.send(
            "post",
            "/categories",
            {"title": "Tech", "tribe_group_id": self.group.id},
        )
        self.assertEqual("pulse.technology", response.json()["code"])
        again = self.send(
            "post",
            "/categories",
            {"title": "Tech 2", "tribe_group_id": self.group.id},
        )
        self.assertEqual(400, again.status_code)

    def test_group_code_already_used_is_a_400(self):
        self.grant()
        HelpRequestCategory.objects.create(
            title="Taken", code=self.group.code, sort_order=30
        )
        response = self.send(
            "post",
            "/categories",
            {"title": "Tech", "tribe_group_id": self.group.id},
        )
        self.assertEqual(400, response.status_code)

    def test_patch_renames_routes_and_turns_off(self):
        self.grant()
        response = self.send(
            "patch",
            f"/categories/{self.first.id}",
            {
                "title": "Renamed",
                "tribe_group_id": self.group.id,
                "is_active": False,
            },
        )
        self.assertEqual(200, response.status_code)
        self.first.refresh_from_db()
        self.assertEqual("Renamed", self.first.title)
        self.assertEqual(self.group, self.first.tribe_group)
        self.assertFalse(self.first.is_active)
        cleared = self.send(
            "patch", f"/categories/{self.first.id}", {"tribe_group_id": None}
        )
        self.assertIsNone(cleared.json()["tribe_group_id"])
        missing = self.send("patch", "/categories/999", {"title": "x"})
        self.assertEqual(404, missing.status_code)

    def test_order_sets_the_panel_order(self):
        self.grant()
        response = self.send(
            "post",
            "/category-order",
            {"ids": [self.second.id, self.first.id]},
        )
        self.assertEqual(
            ["Second", "First"], [c["title"] for c in response.json()]
        )
        partial = self.send(
            "post", "/category-order", {"ids": [self.first.id]}
        )
        self.assertEqual(400, partial.status_code)

    def test_panel_channel(self):
        self.grant()
        snowflake = "1183401618943791186"
        panel = HelpTicketPanel.get_solo()
        panel.message_id = 42
        panel.save(update_fields=["message_id"])
        response = self.send("patch", "/panel", {"channel_id": snowflake})
        self.assertEqual(snowflake, response.json()["channel_id"])
        panel.refresh_from_db()
        self.assertEqual(int(snowflake), panel.channel_id)
        self.assertIsNone(panel.message_id)
        same = self.send("patch", "/panel", {"channel_id": snowflake})
        self.assertEqual(snowflake, same.json()["channel_id"])
        self.assertEqual(
            400, self.send("patch", "/panel", {"channel_id": "0"}).status_code
        )
        self.assertEqual(
            400,
            self.send("patch", "/panel", {"channel_id": "nope"}).status_code,
        )
