"""Operator settings endpoints: permissions and the admin actions they replace."""

import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone

from campaigns.models import CampaignSystem
from campaigns.tests.helpers import auth_headers, grant, make_campaign
from eveonline.models import (
    EveCharacter,
    EveCharacterFwLpPayout,
    FwPayoutEventCode,
)
from feed.models import FeedMonitoredSystem

BASE = "/api/campaigns"


class SettingsApiTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.campaign = make_campaign()
        self.manager = User.objects.create(username="director")
        grant(self.manager, "change_campaign", "view_campaign")
        self.pilot = User.objects.create(username="pilot")
        grant(self.pilot, "view_campaign")
        self.url = f"{BASE}/{self.campaign.slug}"

    def _send(self, method, path, user, body=None):
        kwargs = auth_headers(user)
        if body is not None:
            kwargs["data"] = json.dumps(body)
            kwargs["content_type"] = "application/json"
        return getattr(self.client, method)(path, **kwargs)

    def test_settings_require_manage(self):
        response = self._send("get", f"{self.url}/settings", self.pilot)
        self.assertEqual(response.status_code, 403)
        response = self._send("get", f"{self.url}/settings", self.manager)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["systems"][0]["name"], "Kamela")

    def test_patch_campaign(self):
        denied = self._send(
            "patch", f"{self.url}/settings", self.pilot, {"name": "X"}
        )
        self.assertEqual(denied.status_code, 403)
        response = self._send(
            "patch", f"{self.url}/settings", self.manager, {"name": "Renamed"}
        )
        self.assertEqual(response.status_code, 200)
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.name, "Renamed")

        bad = self._send(
            "patch",
            f"{self.url}/settings",
            self.manager,
            {"end_at": (timezone.now() - timedelta(days=30)).isoformat()},
        )
        self.assertEqual(bad.status_code, 400)

    def test_add_and_retire_system(self):
        FeedMonitoredSystem.objects.create(
            solar_system_id=30003068, name="Kourmonen"
        )
        response = self._send(
            "post",
            f"{self.url}/systems",
            self.manager,
            {"solar_system_id": 30003068, "goal": "hold"},
        )
        self.assertEqual(response.status_code, 200)
        system = CampaignSystem.objects.get(
            campaign=self.campaign, solar_system_id=30003068
        )
        self.assertEqual(system.goal, "hold")

        unknown = self._send(
            "post", f"{self.url}/systems", self.manager, {"solar_system_id": 1}
        )
        self.assertEqual(unknown.status_code, 400)

        response = self._send(
            "delete", f"{self.url}/systems/{system.id}", self.manager
        )
        self.assertEqual(response.status_code, 200)
        system.refresh_from_db()
        self.assertIsNotNone(system.retired_at)

        denied = self._send(
            "delete", f"{self.url}/systems/{system.id}", self.pilot
        )
        self.assertEqual(denied.status_code, 403)

    def test_commander_order_draft_then_publish(self):
        denied = self._send(
            "post", f"{self.url}/commander-order/draft", self.pilot
        )
        self.assertEqual(denied.status_code, 403)

        response = self._send(
            "post", f"{self.url}/commander-order/draft", self.manager
        )
        self.assertEqual(response.status_code, 200)
        self.campaign.refresh_from_db()
        self.assertTrue(self.campaign.commander_order_is_draft)
        self.assertTrue(self.campaign.commander_order_text)

        response = self._send(
            "post", f"{self.url}/commander-order/publish", self.manager
        )
        self.assertEqual(response.status_code, 200)
        self.campaign.refresh_from_db()
        self.assertFalse(self.campaign.commander_order_is_draft)

    def test_publish_refuses_an_empty_order(self):
        response = self._send(
            "post", f"{self.url}/commander-order/publish", self.manager
        )
        self.assertEqual(response.status_code, 400)

    def test_week_target_propose_and_accept(self):
        response = self._send("post", f"{self.url}/week/propose", self.manager)
        self.assertEqual(response.status_code, 200)
        settings = self._send(
            "get", f"{self.url}/settings", self.manager
        ).json()
        for row in settings["week_targets"]:
            response = self._send(
                "patch",
                f"{self.url}/week/{row['id']}",
                self.manager,
                {"target": 5},
            )
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json()["proposed"])


class PayoutCodesApiTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.manager = User.objects.create(username="director")
        grant(self.manager, "change_campaign", "view_campaign")
        self.pilot = User.objects.create(username="pilot")
        grant(self.pilot, "view_campaign")
        FwPayoutEventCode.objects.all().delete()
        self.character = EveCharacter.objects.create(
            character_id=4001, character_name="Seen"
        )

    def _payout(self, notification_id, code, age_days=1):
        EveCharacterFwLpPayout.objects.create(
            character=self.character,
            notification_id=notification_id,
            notification_type="FacWarLPPayoutKill",
            occurred_at=timezone.now() - timedelta(days=age_days),
            amount_lp=500,
            event_code=code,
        )

    def test_requires_manage(self):
        response = self.client.get(
            f"{BASE}/payout-codes", **auth_headers(self.pilot)
        )
        self.assertEqual(response.status_code, 403)
        response = self.client.put(
            f"{BASE}/payout-codes/777",
            data=json.dumps({"site_kind": "complex"}),
            content_type="application/json",
            **auth_headers(self.pilot),
        )
        self.assertEqual(response.status_code, 403)

    def test_lists_unmapped_codes_from_the_last_30_days(self):
        self._payout(1, 777)
        self._payout(2, 777)
        self._payout(3, 888, age_days=45)
        FwPayoutEventCode.objects.create(event_code=359, site_kind="complex")
        self._payout(4, 359)

        response = self.client.get(
            f"{BASE}/payout-codes", **auth_headers(self.manager)
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            [(row["event_code"], row["seen"]) for row in body["unmapped"]],
            [(777, 2)],
        )
        self.assertEqual(body["codes"][0]["seen_30d"], 1)

    def test_add_and_confirm_a_code(self):
        response = self.client.put(
            f"{BASE}/payout-codes/777",
            data=json.dumps(
                {"site_kind": "complex", "label": "Test", "confirmed": True}
            ),
            content_type="application/json",
            **auth_headers(self.manager),
        )
        self.assertEqual(response.status_code, 200)
        row = FwPayoutEventCode.objects.get(event_code=777)
        self.assertTrue(row.confirmed)
        self.assertEqual(row.confirmed_by, "director")

        bad = self.client.put(
            f"{BASE}/payout-codes/777",
            data=json.dumps({"site_kind": "nonsense"}),
            content_type="application/json",
            **auth_headers(self.manager),
        )
        self.assertEqual(bad.status_code, 400)
