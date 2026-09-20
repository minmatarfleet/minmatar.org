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
    CampaignEnlistmentPeriod,
    CampaignEvent,
    CampaignStandingFleet,
    CampaignStatus,
)
from campaigns.services import advantage
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
        grant(
            self.user,
            "view_campaign",
            "add_campaignenlistment",
            "add_campaignevent",
        )
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
            **auth_headers(self.user),
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
            **auth_headers(self.user),
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["formed"])

        response = self.client.get(
            f"{BASE}/{self.campaign.slug}/now", **auth_headers(self.staff)
        )
        gangs = response.json()["gangs_forming"]
        self.assertEqual(len(gangs), 1)
        self.assertEqual(gangs[0]["ships"], "Thrashers")
        self.assertEqual(gangs[0]["started_by"], "pilot")

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


class CampaignAccessTests(TestCase):
    """Every read is as sensitive as the campaign it belongs to."""

    def setUp(self):
        self.client = Client()
        self.campaign = make_campaign()
        self.outsider = User.objects.create(username="outsider")
        self.member, _ = enlist(self.campaign, "member", 7001)
        grant(self.member, "view_campaign", "add_campaignenlistment")

    def _subresources(self):
        return [
            "/now",
            "/week",
            "/orders",
            "/systems",
            "/leaderboard",
            "/killmails",
            "/sites",
            "/timeline",
            "/roster",
        ]

    def test_an_anonymous_visitor_cannot_read_any_sub_resource(self):
        for path in self._subresources():
            response = self.client.get(f"{BASE}/{self.campaign.slug}{path}")
            self.assertEqual(response.status_code, 403, path)

    def test_a_pilot_without_the_feature_cannot_read_them_either(self):
        for path in self._subresources():
            response = self.client.get(
                f"{BASE}/{self.campaign.slug}{path}",
                **auth_headers(self.outsider),
            )
            self.assertEqual(response.status_code, 403, path)

    def test_a_pilot_with_the_feature_can(self):
        for path in self._subresources():
            response = self.client.get(
                f"{BASE}/{self.campaign.slug}{path}",
                **auth_headers(self.member),
            )
            self.assertEqual(response.status_code, 200, path)

    def test_a_public_campaign_is_readable_without_the_feature(self):
        self.campaign.visibility = "public"
        self.campaign.save()
        response = self.client.get(f"{BASE}/{self.campaign.slug}/roster")
        self.assertEqual(response.status_code, 200)

    def test_a_negative_page_size_is_clamped_not_crashed(self):
        for limit in (-1, 0, 10_000_000):
            response = self.client.get(
                f"{BASE}/{self.campaign.slug}/killmails?limit={limit}",
                **auth_headers(self.member),
            )
            self.assertEqual(response.status_code, 200, limit)


class CampaignWriteGuardTests(TestCase):
    """Holding a feature is not the same as being in the campaign."""

    def setUp(self):
        self.client = Client()
        self.campaign = make_campaign()
        self.member, _ = enlist(self.campaign, "member", 7101)
        grant(
            self.member,
            "view_campaign",
            "add_campaignenlistment",
            "add_campaignevent",
        )
        self.bystander = User.objects.create(username="bystander")
        grant(
            self.bystander,
            "view_campaign",
            "add_campaignenlistment",
            "add_campaignevent",
        )
        self.system = self.campaign.systems.first()

    def test_a_non_participant_cannot_report_advantage(self):
        response = self.client.post(
            f"{BASE}/{self.campaign.slug}/systems/{self.system.id}/advantage",
            data={"our_pct": 40.0, "enemy_pct": 10.0},
            content_type="application/json",
            **auth_headers(self.bystander),
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "not_enlisted")

    def test_a_non_participant_cannot_take_the_standing_fleet(self):
        response = self.client.post(
            f"{BASE}/{self.campaign.slug}/standing-fleet/take",
            **auth_headers(self.bystander),
        )
        self.assertEqual(response.status_code, 403)

    def test_a_non_participant_cannot_form_a_gang(self):
        response = self.client.post(
            f"{BASE}/{self.campaign.slug}/gangs",
            data={"ships": "Thrashers"},
            content_type="application/json",
            **auth_headers(self.bystander),
        )
        self.assertEqual(response.status_code, 403)

    def test_a_participant_can(self):
        response = self.client.post(
            f"{BASE}/{self.campaign.slug}/gangs",
            data={"ships": "Thrashers"},
            content_type="application/json",
            **auth_headers(self.member),
        )
        self.assertEqual(response.status_code, 200)

    def test_a_finished_campaign_accepts_no_writes(self):
        self.campaign.status = CampaignStatus.COMPLETED
        self.campaign.save()
        response = self.client.post(
            f"{BASE}/{self.campaign.slug}/gangs",
            data={"ships": "Thrashers"},
            content_type="application/json",
            **auth_headers(self.member),
        )
        self.assertEqual(response.status_code, 409)

    def test_oversized_gang_text_is_rejected_not_a_500(self):
        response = self.client.post(
            f"{BASE}/{self.campaign.slug}/gangs",
            data={"ships": "T" * 400},
            content_type="application/json",
            **auth_headers(self.member),
        )
        self.assertEqual(response.status_code, 422)

    def test_an_out_of_range_digest_hour_is_rejected(self):
        response = self.client.post(
            f"{BASE}/{self.campaign.slug}/enlist",
            data={"digest_hour": 99999},
            content_type="application/json",
            **auth_headers(self.member),
        )
        self.assertEqual(response.status_code, 422)

    def test_readiness_refuses_an_offsite_redirect(self):
        response = self.client.get(
            f"{BASE}/readiness?redirect_url=https://evil.example/x",
            **auth_headers(self.member),
        )
        self.assertEqual(response.status_code, 200)
        for row in response.json()["characters"]:
            self.assertNotIn("evil.example", row["action_url"])


class StandingFleetTests(TestCase):
    """The fleet has to be flyable by whoever is recorded as holding it."""

    def setUp(self):
        self.client = Client()
        self.campaign = make_campaign()
        self.pilot, self.character = enlist(self.campaign, "boss", 7201)
        grant(self.pilot, "view_campaign", "add_campaignenlistment")

        self.no_character = User.objects.create(username="lurker")
        grant(self.no_character, "view_campaign", "add_campaignenlistment")
        enlistment = CampaignEnlistment.objects.create(
            campaign=self.campaign, user=self.no_character, status="active"
        )
        CampaignEnlistmentPeriod.objects.create(
            enlistment=enlistment, enlisted_at=self.campaign.start_at
        )

    def _take(self, user):
        return self.client.post(
            f"{BASE}/{self.campaign.slug}/standing-fleet/take",
            **auth_headers(user),
        )

    def test_a_pilot_with_a_character_can_take_it(self):
        response = self._take(self.pilot)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["taken"])

        standing = CampaignStandingFleet.objects.get(campaign=self.campaign)
        self.assertEqual(standing.current_boss_user_id, self.pilot.id)
        self.assertEqual(standing.current_boss_character_id, 7201)
        self.assertTrue(standing.is_up)

    def test_a_pilot_with_no_character_is_refused(self):
        """Otherwise the fleet is held by somebody who cannot boss it."""
        response = self._take(self.no_character)
        self.assertEqual(response.status_code, 409)
        self.assertFalse(
            CampaignStandingFleet.objects.filter(
                campaign=self.campaign,
                current_boss_user=self.no_character,
            ).exists()
        )

    def test_retaking_a_fleet_you_already_hold_is_not_a_handover(self):
        """Uptime and handovers are launch KPIs, so they cannot be inflated."""
        self._take(self.pilot)
        first = CampaignStandingFleet.objects.get(
            campaign=self.campaign
        ).handovers

        for _ in range(5):
            self._take(self.pilot)

        self.assertEqual(
            CampaignStandingFleet.objects.get(
                campaign=self.campaign
            ).handovers,
            first,
        )


class AdvantageConsensusTests(TestCase):
    """One pilot, one vote."""

    def setUp(self):
        self.campaign = make_campaign()
        self.system = self.campaign.systems.first()
        self.loud, _ = enlist(self.campaign, "loud", 7301)
        self.quiet, _ = enlist(self.campaign, "quiet", 7302)

    def test_repeating_a_reading_does_not_outvote_the_alliance(self):
        advantage.record_reading(self.system, self.quiet, 20.0, 10.0)
        for _ in range(20):
            advantage.record_reading(self.system, self.loud, 40.0, 10.0)

        _, state_row = advantage.record_reading(
            self.system, self.loud, 40.0, 10.0
        )
        state = advantage.as_card(state_row)
        # Two pilots, so the agreed reading sits between them, not on top of
        # whoever pressed the button most.
        self.assertAlmostEqual(state["our_pct"], 30.0, places=1)

    def test_a_wild_reading_is_still_held(self):
        advantage.record_reading(self.system, self.quiet, 20.0, 10.0)
        reading, _ = advantage.record_reading(
            self.system, self.loud, 99.0, 0.0
        )
        self.assertEqual(reading.status, "held")

    def test_reporting_returns_the_reading_you_just_made(self):
        """Not the one from before it.

        Django caches a reverse one-to-one on the instance, so reading the
        state back off the system after writing it hands you the stale row.
        """
        client = Client()
        grant(self.loud, "view_campaign", "add_campaignenlistment")

        response = client.post(
            f"{BASE}/{self.campaign.slug}/systems/{self.system.id}/advantage",
            data={"our_pct": 65.0, "enemy_pct": 5.0},
            content_type="application/json",
            **auth_headers(self.loud),
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["our_pct"], 65.0)
        self.assertEqual(response.json()["net_pct"], 60.0)

    def test_the_first_reading_of_a_system_is_accepted(self):
        reading, _ = advantage.record_reading(
            self.system, self.loud, 80.0, 5.0
        )
        self.assertEqual(reading.status, "accepted")
