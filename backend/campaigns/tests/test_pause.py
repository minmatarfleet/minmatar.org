"""Pausing a faction warfare campaign: kills count, the week stands still."""

import json

from django.core.cache import cache
from django.utils import timezone

from django.contrib.auth.models import User
from django.test import Client, TestCase

from campaigns.models import (
    CampaignKillmail,
    CampaignKind,
    CampaignStatus,
    CampaignSystemSnapshot,
    CampaignWeekTarget,
)
from campaigns.services import awards, plan
from campaigns.services.attribution import attribute_feed_killmail
from campaigns.tests.helpers import (
    auth_headers,
    enlist,
    grant,
    make_campaign,
    make_feed_killmail,
)

BASE = "/api/campaigns"


class PauseSettingsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.manager = User.objects.create(username="director")
        grant(self.manager, "change_campaign", "view_campaign")

    def _patch(self, campaign, body):
        return self.client.patch(
            f"{BASE}/{campaign.slug}/settings",
            data=json.dumps(body),
            content_type="application/json",
            **auth_headers(self.manager),
        )

    def test_pause_and_resume_a_faction_warfare_campaign(self):
        campaign = make_campaign()
        response = self._patch(campaign, {"status": "paused"})
        self.assertEqual(response.status_code, 200)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, CampaignStatus.PAUSED)
        self.assertIsNotNone(campaign.paused_at)

        detail = self.client.get(
            f"{BASE}/{campaign.slug}", **auth_headers(self.manager)
        ).json()
        self.assertEqual(detail["status"], "paused")
        self.assertIsNotNone(detail["paused_at"])

        self._patch(campaign, {"status": "active"})
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, CampaignStatus.ACTIVE)
        self.assertIsNone(campaign.paused_at)

    def test_a_strategic_campaign_cannot_pause(self):
        campaign = make_campaign(kind=CampaignKind.STRATEGIC)
        response = self._patch(campaign, {"status": "paused"})
        self.assertEqual(response.status_code, 400)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, CampaignStatus.ACTIVE)


class PausedCampaignTestCase(TestCase):
    def setUp(self):
        self.campaign = make_campaign(status=CampaignStatus.PAUSED)
        enlist(self.campaign, "pilot", 4001)

    def test_kills_still_count(self):
        mail = make_feed_killmail(
            11, victim_character_id=9999, attacker_ids=[4001]
        )
        self.assertEqual(attribute_feed_killmail(mail), 1)
        self.assertTrue(CampaignKillmail.objects.filter(killmail_id=11))

    def test_no_targets_orders_or_week_awards(self):
        self.assertEqual(plan.propose_week(self.campaign), 0)
        self.assertFalse(CampaignWeekTarget.objects.exists())
        self.assertEqual(plan.generate_orders(self.campaign), 0)
        self.assertEqual(awards.close_week(self.campaign), 0)


class PausedOverlayTestCase(TestCase):
    """The window keeps a paused campaign; every objective reads Paused."""

    def test_paused_rows_read_paused(self):
        cache.clear()
        campaign = make_campaign(status=CampaignStatus.PAUSED)
        user, _ = enlist(campaign, "pilot", 4001)
        grant(user, "view_campaign")
        CampaignSystemSnapshot.objects.create(
            campaign_system=campaign.systems.first(),
            captured_at=timezone.now(),
            victory_points=1860,
            victory_points_threshold=3000,
            contested_percent=62,
            occupier_faction_id=500003,
            owner_faction_id=500003,
        )
        response = (
            Client()
            .get(f"{BASE}/overlay", **auth_headers(user))
            .json()["campaign"]
        )
        self.assertEqual(response["slug"], campaign.slug)
        self.assertTrue(response["systems"])
        self.assertEqual(
            {row["objective_label"] for row in response["systems"]},
            {"Paused"},
        )


class OverlayCampaignListTestCase(TestCase):
    """The window's switcher lists every live campaign, paused included."""

    def test_live_and_paused_listed_drafts_and_done_not(self):
        cache.clear()
        live = make_campaign()
        make_campaign(
            slug="paused-one", short_code="PSD", status=CampaignStatus.PAUSED
        )
        make_campaign(
            slug="done-one", short_code="DON", status=CampaignStatus.COMPLETED
        )
        make_campaign(
            slug="draft-one", short_code="DRF", status=CampaignStatus.DRAFT
        )
        user, _ = enlist(live, "pilot", 4002)
        grant(user, "view_campaign")
        body = Client().get(f"{BASE}/overlay", **auth_headers(user)).json()
        self.assertEqual(body["campaign"]["slug"], live.slug)
        self.assertEqual(
            sorted(row["slug"] for row in body["campaigns"]),
            ["paused-one", "test-push"],
        )
        row = next(r for r in body["campaigns"] if r["slug"] == "paused-one")
        self.assertEqual(row["status"], "paused")
        self.assertEqual(
            set(row["totals"]),
            {"structures_destroyed", "isk_destroyed", "ships_killed"},
        )
