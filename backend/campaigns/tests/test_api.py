"""API smoke tests: permissions, shapes and the enlistment round trip."""

from datetime import timedelta

import jwt
from django.conf import settings
from django.contrib.auth.models import Permission, User
from django.test import Client, TestCase
from django.utils import timezone

from campaigns.models import (
    CampaignEnlistment,
    CampaignEnlistmentCharacter,
    CampaignEvent,
    CampaignStatus,
)
from campaigns.tests.helpers import enlist, make_campaign
from eveonline.models import EveCharacter


def grant(user: User, *codenames: str) -> None:
    """Give a user the legacy permissions a campaign feature falls back to."""
    for codename in codenames:
        permission = Permission.objects.filter(
            content_type__app_label="campaigns", codename=codename
        ).first()
        if permission:
            user.user_permissions.add(permission)
    user.refresh_from_db()


BASE = "/api/campaigns"


def auth_headers(user: User) -> dict:
    token = jwt.encode(
        {"user_id": user.pk}, settings.SECRET_KEY, algorithm="HS256"
    )
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


class CampaignApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.campaign = make_campaign()
        self.user, self.character = enlist(self.campaign, "pilot", 3001)
        grant(self.user, "view_campaign", "add_campaignenlistment")
        self.staff = User.objects.create(username="staff", is_superuser=True)

    def test_listing_requires_permission(self):
        """An anonymous visitor is told no, not handed an empty list."""
        response = self.client.get(f"{BASE}")
        self.assertEqual(response.status_code, 403)

    def test_a_pilot_without_the_feature_is_refused(self):
        outsider = User.objects.create(username="outsider")
        response = self.client.get(f"{BASE}", **auth_headers(outsider))
        self.assertEqual(response.status_code, 403)

    def test_staff_can_list_campaigns(self):
        response = self.client.get(f"{BASE}", **auth_headers(self.staff))
        self.assertEqual(response.status_code, 200)
        slugs = [row["slug"] for row in response.json()]
        self.assertIn(self.campaign.slug, slugs)

    def test_detail_carries_totals_and_systems(self):
        response = self.client.get(
            f"{BASE}/{self.campaign.slug}", **auth_headers(self.staff)
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["short_code"], "TST")
        self.assertIn("totals", body)
        self.assertEqual(
            [system["name"] for system in body["systems"]], ["Kamela"]
        )

    def test_draft_campaigns_are_hidden_from_ordinary_pilots(self):
        self.campaign.status = CampaignStatus.DRAFT
        self.campaign.save()
        response = self.client.get(
            f"{BASE}/{self.campaign.slug}", **auth_headers(self.user)
        )
        self.assertEqual(response.status_code, 404)

    def test_readiness_lists_every_character_with_its_state(self):
        response = self.client.get(
            f"{BASE}/readiness", **auth_headers(self.user)
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 1)
        row = body["characters"][0]
        self.assertEqual(row["character_name"], "Pilot")
        # No token at all, so it counts for nothing and needs one action.
        self.assertEqual(row["state"], "lapsed")

    def test_readiness_route_is_not_swallowed_by_the_slug_route(self):
        """``/readiness`` must not resolve as a campaign called readiness."""
        response = self.client.get(
            f"{BASE}/readiness", **auth_headers(self.user)
        )
        self.assertIn("characters", response.json())

    def test_a_pilot_can_enlist_and_leave(self):
        newcomer = User.objects.create(username="newcomer")
        grant(newcomer, "view_campaign", "add_campaignenlistment")
        EveCharacter.objects.create(
            character_id=3002, character_name="Newcomer", user=newcomer
        )

        response = self.client.post(
            f"{BASE}/{self.campaign.slug}/enlist",
            data={"source": "web"},
            content_type="application/json",
            **auth_headers(newcomer),
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["enlisted"])
        self.assertEqual(body["characters_included"], 1)
        # No campaign token yet, so we say so rather than silently dropping it.
        self.assertEqual(body["characters_missing_scopes"], ["Newcomer"])

        enlistment = CampaignEnlistment.objects.get(
            campaign=self.campaign, user=newcomer
        )
        self.assertEqual(enlistment.periods.count(), 1)

        response = self.client.delete(
            f"{BASE}/{self.campaign.slug}/enlist", **auth_headers(newcomer)
        )
        self.assertEqual(response.status_code, 200)
        enlistment.refresh_from_db()
        self.assertEqual(enlistment.status, "left")
        self.assertIsNotNone(enlistment.periods.first().left_at)

    def test_excluding_a_character_closes_its_inclusion_period(self):
        response = self.client.delete(
            f"{BASE}/{self.campaign.slug}/characters/3001",
            **auth_headers(self.user),
        )
        self.assertEqual(response.status_code, 200)
        row = CampaignEnlistmentCharacter.objects.get(character=self.character)
        self.assertIsNotNone(row.included_until)

    def test_re_enlisting_after_excluding_a_character_does_not_break(self):
        """A character can be excluded and re-included many times.

        Each cycle opens a new inclusion period, so anything that assumes one
        row per character falls over the second time round.
        """
        url = f"{BASE}/{self.campaign.slug}/characters/3001"
        for _ in range(2):
            self.assertEqual(
                self.client.delete(url, **auth_headers(self.user)).status_code,
                200,
            )
            self.assertEqual(
                self.client.put(url, **auth_headers(self.user)).status_code,
                200,
            )

        response = self.client.post(
            f"{BASE}/{self.campaign.slug}/enlist",
            data={"source": "web"},
            content_type="application/json",
            **auth_headers(self.user),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["characters_included"], 1)

        open_rows = CampaignEnlistmentCharacter.objects.filter(
            enlistment__campaign=self.campaign,
            character=self.character,
            included_until__isnull=True,
        )
        self.assertEqual(open_rows.count(), 1)

    def test_reporting_advantage_records_a_reading(self):
        system = self.campaign.systems.first()
        response = self.client.post(
            f"{BASE}/{self.campaign.slug}/systems/{system.id}/advantage",
            data={"our_pct": 40.0, "enemy_pct": 15.0},
            content_type="application/json",
            **auth_headers(self.staff),
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["accepted"])
        self.assertEqual(body["net_pct"], 25.0)

    def test_leaderboard_and_timeline_respond(self):
        for path in ("/leaderboard", "/timeline", "/killmails", "/sites"):
            response = self.client.get(
                f"{BASE}/{self.campaign.slug}{path}",
                **auth_headers(self.staff),
            )
            self.assertEqual(response.status_code, 200, path)
            self.assertIsInstance(response.json(), list)

    def test_forming_a_gang_puts_it_on_the_right_now_strip(self):
        response = self.client.post(
            f"{BASE}/{self.campaign.slug}/gangs",
            data={"ships": "Thrashers", "note": "Kamela roam"},
            content_type="application/json",
            **auth_headers(self.staff),
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["formed"])

        response = self.client.get(
            f"{BASE}/{self.campaign.slug}/now", **auth_headers(self.staff)
        )
        gangs = response.json()["gangs_forming"]
        self.assertEqual(len(gangs), 1)
        self.assertEqual(gangs[0]["ships"], "Thrashers")
        self.assertEqual(gangs[0]["started_by"], "staff")

    def test_a_stale_gang_drops_off_the_strip(self):
        CampaignEvent.objects.create(
            campaign=self.campaign,
            kind=CampaignEvent.Kind.GANG_FORMED,
            occurred_at=timezone.now() - timedelta(hours=5),
            title="Old gang",
            is_active=True,
        )
        response = self.client.get(
            f"{BASE}/{self.campaign.slug}/now", **auth_headers(self.staff)
        )
        self.assertEqual(response.json()["gangs_forming"], [])

    def test_roster_reports_coverage_for_every_hour(self):
        response = self.client.get(
            f"{BASE}/{self.campaign.slug}/roster", **auth_headers(self.staff)
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["coverage"]), 24)
