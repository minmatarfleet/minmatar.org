"""The daily fleet roundup settings on a tribe group."""

from django.core.cache import cache
from django.test import Client

from app.test import TestCase
from app.testing import make_token
from tribes.models import TribeGroupChief
from tribes.tests.publishing_fixtures import (
    add_member,
    make_tribe_group,
    make_user,
)


class GroupRoundupSettingsTests(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.group = make_tribe_group()
        self.member = make_user("member")
        add_member(self.group, self.member)
        self.chief = make_user("chief")
        TribeGroupChief.objects.create(
            tribe_group=self.group, region="US", user=self.chief
        )
        self.path = f"/api/tribes/groups/{self.group.id}/publishing"

    def call(self, method, user, data=None):
        kwargs = {"HTTP_AUTHORIZATION": f"Bearer {make_token(user)}"}
        if data is not None:
            kwargs["data"] = data
            kwargs["content_type"] = "application/json"
        return getattr(Client(), method)(self.path, **kwargs)

    def test_defaults_off_at_20(self):
        body = self.call("get", self.chief).json()
        self.assertFalse(body["roundup_enabled"])
        self.assertEqual(body["roundup_hour"], 20)
        self.group.refresh_from_db()
        self.assertIsNone(self.group.roundup_last_sent_on)

    def test_manager_turns_on_and_sets_hour(self):
        response = self.call(
            "patch",
            self.chief,
            {"roundup_enabled": True, "roundup_hour": 18},
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["roundup_enabled"])
        self.assertEqual(response.json()["roundup_hour"], 18)
        self.group.refresh_from_db()
        self.assertTrue(self.group.roundup_enabled)
        self.assertEqual(self.group.roundup_hour, 18)

    def test_hour_out_of_range_is_rejected(self):
        for hour in (24, -1):
            response = self.call("patch", self.chief, {"roundup_hour": hour})
            self.assertIn(response.status_code, (400, 422), hour)
        self.group.refresh_from_db()
        self.assertEqual(self.group.roundup_hour, 20)

    def test_non_manager_403(self):
        response = self.call("patch", self.member, {"roundup_enabled": True})
        self.assertEqual(response.status_code, 403)
