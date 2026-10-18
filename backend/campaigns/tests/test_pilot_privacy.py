"""Public campaign reads name pilots by their main, never their web login.

``User.username`` is the member's Discord handle. A campaign marked public
is readable anonymously, so nothing it returns may carry that handle.
"""

import importlib
from datetime import timedelta

import factory
from django.apps import apps as django_apps
from django.db.models import signals
from django.test import Client, TestCase
from django.utils import timezone

from campaigns.helpers import campaign_week_start
from campaigns.models import (
    CampaignAward,
    CampaignEvent,
    CampaignParticipantDay,
    CampaignSiteCompletion,
)
from campaigns.services import awards, stats
from campaigns.tests.helpers import auth_headers, enlist, grant, make_campaign
from eveonline.models import EveCharacterFwLpPayout, EvePlayer
from fleets.models import EveFleet

BASE = "/api/campaigns"
HANDLE = "secret_discord_handle"
NO_MAIN_HANDLE = "another_discord_handle"


class PublicCampaignPilotNameTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.campaign = make_campaign(visibility="public")
        self.user, self.character = enlist(self.campaign, HANDLE, 8001)
        self.character.character_name = "Main Pilot"
        self.character.save()
        EvePlayer.objects.create(
            user=self.user, nickname="x", primary_character=self.character
        )
        grant(
            self.user,
            "view_campaign",
            "add_campaignenlistment",
            "add_campaignevent",
        )
        # A pilot with no primary character must not fall back to a handle.
        self.no_main, _ = enlist(self.campaign, NO_MAIN_HANDLE, 8002)

        week_start = campaign_week_start()
        for user, kills in ((self.user, 5), (self.no_main, 3)):
            CampaignParticipantDay.objects.create(
                campaign=self.campaign,
                user=user,
                day=week_start,
                kills=kills,
                complexes=kills,
            )
        awards.close_week(self.campaign, week_start)

        payout = EveCharacterFwLpPayout.objects.create(
            character=self.character,
            notification_id=1,
            notification_type="FWLPPayout",
            occurred_at=timezone.now(),
            amount_lp=1000,
            event_code=359,
        )
        CampaignSiteCompletion.objects.create(
            campaign=self.campaign,
            payout=payout,
            user=self.user,
            character_id=self.character.character_id,
            campaign_system=self.campaign.systems.first(),
            occurred_at=timezone.now(),
            amount_lp=1000,
            event_code=359,
        )

        response = self.client.post(
            f"{BASE}/{self.campaign.slug}/gangs",
            data={"ships": "Thrashers", "note": "roam"},
            content_type="application/json",
            **auth_headers(self.user),
        )
        self.assertEqual(response.status_code, 200)

    def _get(self, path):
        response = self.client.get(f"{BASE}/{self.campaign.slug}{path}")
        self.assertEqual(response.status_code, 200, path)
        return response

    def test_no_anonymous_read_carries_a_username(self):
        for path in (
            "/now",
            "/leaderboard",
            "/leaderboard?metric=complexes",
            "/sites",
            "/timeline",
            "/awards",
            "/roster",
            "/fleets",
        ):
            body = self._get(path).content.decode()
            self.assertNotIn(HANDLE, body, path)
            self.assertNotIn(NO_MAIN_HANDLE, body, path)
            self.assertNotIn('"username"', body, path)

    def test_leaderboard_names_the_main(self):
        rows = self._get("/leaderboard").json()
        self.assertEqual(
            [(row["character_name"], row["value"]) for row in rows],
            [("Main Pilot", 5.0), ("", 3.0)],
        )

    def test_award_rows_and_titles_name_the_main(self):
        rows = self._get("/awards").json()
        self.assertTrue(rows)
        self.assertEqual(
            {row["character_name"] for row in rows}, {"Main Pilot"}
        )
        titles = CampaignEvent.objects.filter(
            campaign=self.campaign, kind=CampaignEvent.Kind.AWARD
        ).values_list("title", flat=True)
        self.assertIn("Top Gun: Main Pilot", titles)

    def test_an_award_for_a_pilot_without_a_main_has_no_name(self):
        award = CampaignAward.objects.filter(campaign=self.campaign).first()
        award.user = self.no_main
        award.save()
        rows = self._get("/awards").json()
        self.assertIn("", [row["character_name"] for row in rows])

    def test_a_title_for_a_pilot_without_a_main_says_unknown(self):
        self.assertEqual(stats.pilot_name(self.no_main.id), "Unknown pilot")
        self.assertEqual(stats.pilot_name(None), "Unknown pilot")

    def test_gang_title_and_strip_name_the_main(self):
        gang = CampaignEvent.objects.get(
            campaign=self.campaign, kind=CampaignEvent.Kind.GANG_FORMED
        )
        self.assertEqual(gang.title, "Main Pilot is forming Thrashers")
        strip = self._get("/now").json()["gangs_forming"]
        self.assertEqual(strip[0]["started_by"], "Main Pilot")

    def test_fleet_commander_falls_back_to_the_creators_main(self):
        with factory.django.mute_signals(signals.pre_save, signals.post_save):
            fleet = EveFleet.objects.create(
                type="strategic",
                start_time=timezone.now() - timedelta(hours=1),
                campaign=self.campaign,
                created_by=self.user,
            )
        rows = self._get("/fleets").json()
        self.assertEqual(
            [(row["id"], row["fleet_commander"]) for row in rows],
            [(fleet.id, "Main Pilot")],
        )


class EventTitleMigrationTests(TestCase):
    """0031 rewrites stored titles and puts the old text back on reverse."""

    def setUp(self):
        self.migration = importlib.import_module(
            "campaigns.migrations.0031_pilot_names_in_event_titles"
        )
        self.campaign = make_campaign()
        self.user, self.character = enlist(self.campaign, HANDLE, 8101)
        self.character.character_name = "Main Pilot"
        self.character.save()
        EvePlayer.objects.create(
            user=self.user, nickname="x", primary_character=self.character
        )
        self.no_main, _ = enlist(self.campaign, NO_MAIN_HANDLE, 8102)

        def event(kind, title, user, **payload):
            return CampaignEvent.objects.create(
                campaign=self.campaign,
                kind=kind,
                occurred_at=timezone.now(),
                title=title,
                user=user,
                payload=payload,
            )

        self.award = event(
            CampaignEvent.Kind.AWARD,
            f"Top Gun: {HANDLE}",
            self.user,
            metric="kills",
        )
        self.gang = event(
            CampaignEvent.Kind.GANG_FORMED,
            f"{NO_MAIN_HANDLE} is forming Thrashers",
            self.no_main,
            ships="Thrashers",
        )
        # A title that does not carry the handle is left alone.
        self.other = event(
            CampaignEvent.Kind.AWARD, "Hand-written title", self.user
        )
        self.feed = event(
            CampaignEvent.Kind.HOSTILE_GANG, f"{HANDLE} spotted", self.user
        )

    def _run(self, name):
        getattr(self.migration, name)(django_apps, None)
        for event in (self.award, self.gang, self.other, self.feed):
            event.refresh_from_db()

    def test_forwards_names_the_main_and_keeps_the_old_title(self):
        self._run("forwards")
        self.assertEqual(self.award.title, "Top Gun: Main Pilot")
        self.assertEqual(
            self.award.payload,
            {"metric": "kills", "legacy_title": f"Top Gun: {HANDLE}"},
        )
        self.assertEqual(self.gang.title, "Unknown pilot is forming Thrashers")
        self.assertEqual(self.gang.payload["ships"], "Thrashers")
        self.assertEqual(self.other.title, "Hand-written title")
        self.assertNotIn("legacy_title", self.other.payload)
        self.assertEqual(self.feed.title, f"{HANDLE} spotted")

    def test_forwards_twice_is_a_no_op(self):
        self._run("forwards")
        self._run("forwards")
        self.assertEqual(
            self.award.payload["legacy_title"], f"Top Gun: {HANDLE}"
        )

    def test_backwards_restores_every_title_exactly(self):
        self._run("forwards")
        self._run("backwards")
        self.assertEqual(self.award.title, f"Top Gun: {HANDLE}")
        self.assertEqual(self.award.payload, {"metric": "kills"})
        self.assertEqual(
            self.gang.title, f"{NO_MAIN_HANDLE} is forming Thrashers"
        )
        self.assertEqual(self.gang.payload, {"ships": "Thrashers"})
