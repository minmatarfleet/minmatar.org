"""What the redesigned campaign forms need from the API: labels, derived codes, names."""

import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone

from campaigns.models import Campaign, CampaignParty
from campaigns.tests.helpers import auth_headers, grant, make_campaign
from eveonline.models import EveAlliance
from feed.models import FeedMonitoredSystem

BASE = "/api/campaigns"


class FormSupportTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.manager = User.objects.create(username="director")
        grant(self.manager, "add_campaign", "change_campaign", "view_campaign")
        FeedMonitoredSystem.objects.create(
            solar_system_id=30003068, name="Kourmonen"
        )

    def _post(self, path, body):
        return self.client.post(
            path,
            data=json.dumps(body),
            content_type="application/json",
            **auth_headers(self.manager),
        )

    def _create(self, **overrides):
        now = timezone.now()
        body = {
            "name": "Huola Push",
            "slug": "huola-push",
            "kind": "faction_warfare",
            "start_at": now.isoformat(),
            "end_at": (now + timedelta(days=14)).isoformat(),
            "system_ids": [30003068],
        }
        body.update(overrides)
        return self._post(BASE, body)

    def test_choices_carry_the_model_labels(self):
        response = self.client.get(
            f"{BASE}/choices", **auth_headers(self.manager)
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn({"value": "none", "label": "No goal"}, body["goal"])
        self.assertIn(
            {"value": "advantage_site", "label": "Advantage site"},
            body["site_kind"],
        )
        self.assertEqual(
            [row["value"] for row in body["kind"]],
            ["faction_warfare", "strategic"],
        )

    def test_create_derives_a_unique_short_code(self):
        make_campaign(slug="older", short_code="HP")
        response = self._create()
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["short_code"], "HP2")

        response = self._create(slug="given", short_code="hpx")
        self.assertEqual(response.json()["short_code"], "HPX")

    def test_faction_warfare_needs_a_warzone_system(self):
        response = self._create(system_ids=[])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "Faction Warfare needs at least one warzone system.",
        )
        self.assertFalse(Campaign.objects.filter(slug="huola-push").exists())

        response = self._create(system_ids=[30000142])
        self.assertEqual(response.status_code, 400)
        self.assertIn("warzone", response.json()["detail"])

        response = self._create(kind="strategic", system_ids=[])
        self.assertEqual(response.status_code, 200)

    def test_party_picked_by_id_takes_the_known_ticker(self):
        campaign = make_campaign()
        EveAlliance.objects.create(
            alliance_id=99000001, name="Amarr Defense", ticker="AMD"
        )
        response = self._post(
            f"{BASE}/{campaign.slug}/parties",
            {
                "name": "Amarr Defense",
                "kind": "alliance",
                "side": "enemy",
                "alliance_id": 99000001,
            },
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["ticker"], "AMD")
        self.assertEqual(CampaignParty.objects.get().ticker, "AMD")
