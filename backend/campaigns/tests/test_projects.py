"""Corporation projects on the corporation page and put toward campaigns."""

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase
from django.utils import timezone

from campaigns.models import CampaignProject, CampaignStatus
from campaigns.tests.helpers import auth_headers, grant, make_campaign
from eveonline.models import (
    EveCharacter,
    EveCorporation,
    EveCorporationProject,
    EveCorporationProjectContributor,
)

PROJECT_ID = "3868eaed-8278-4cb7-9709-7d7de9c20dc7"
CORPS = "/api/eveonline/corporations/corporations"
CAMPAIGNS = "/api/campaigns"


class CorporationProjectApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.campaign = make_campaign()
        self.corporation = EveCorporation.objects.create(
            corporation_id=98000001, name="Rattini Tribe"
        )
        self.director = User.objects.create(username="director")
        director_character = EveCharacter.objects.create(
            character_id=9001,
            character_name="Director Dan",
            corporation_id=98000001,
            user=self.director,
        )
        self.corporation.directors.add(director_character)
        self.outsider = User.objects.create(username="outsider")
        grant(self.outsider, "view_campaign")
        self.project = EveCorporationProject.objects.create(
            project_id=PROJECT_ID,
            corporation=self.corporation,
            name="Kill Amarr frigates",
            state="Completed",
            kind="destroy_ship",
            progress_current=20,
            progress_desired=20,
            reward_initial=100_000_000.0,
            reward_remaining=0.0,
            last_modified=timezone.now(),
        )
        EveCorporationProjectContributor.objects.create(
            project=self.project,
            character_id=9101,
            character_name="Pilot One",
            contributed=12,
        )
        EveCorporationProjectContributor.objects.create(
            project=self.project,
            character_id=9102,
            character_name="Pilot Two",
            contributed=8,
        )

    def _attach(self, user, campaign=None):
        campaign = campaign or self.campaign
        return self.client.post(
            f"{CAMPAIGNS}/{campaign.slug}/projects",
            {"project_id": PROJECT_ID},
            content_type="application/json",
            **auth_headers(user),
        )

    def test_director_sees_projects_and_open_campaigns(self):
        response = self.client.get(
            f"{CORPS}/98000001/projects", **auth_headers(self.director)
        )
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertTrue(body["can_manage"])
        self.assertFalse(body["has_token"])
        self.assertEqual(["test-push"], [c["slug"] for c in body["campaigns"]])
        project = body["projects"][0]
        self.assertEqual("Rattini Tribe", project["corporation_name"])
        self.assertEqual(2, len(project["contributors"]))
        self.assertEqual([], project["campaigns"])

    def test_outsiders_cannot_see_corporation_projects(self):
        response = self.client.get(
            f"{CORPS}/98000001/projects", **auth_headers(self.outsider)
        )
        self.assertEqual(403, response.status_code)

    def test_access_flags(self):
        director = self.client.get(
            f"{CORPS}/98000001/members/access", **auth_headers(self.director)
        ).json()
        self.assertTrue(director["can_view_projects"])
        self.assertTrue(director["can_manage_projects"])
        outsider = self.client.get(
            f"{CORPS}/98000001/members/access", **auth_headers(self.outsider)
        ).json()
        self.assertFalse(outsider["can_view_projects"])
        self.assertFalse(outsider["can_manage_projects"])

    def test_director_attaches_without_approval(self):
        self.assertEqual(201, self._attach(self.director).status_code)
        self.assertEqual(200, self._attach(self.director).status_code)
        self.assertEqual(1, CampaignProject.objects.count())

        body = self.client.get(
            f"{CORPS}/98000001/projects", **auth_headers(self.director)
        ).json()
        self.assertEqual(
            ["test-push"],
            [c["slug"] for c in body["projects"][0]["campaigns"]],
        )

    def test_only_the_corporations_leadership_attaches(self):
        self.assertEqual(403, self._attach(self.outsider).status_code)
        self.assertFalse(CampaignProject.objects.exists())

    def test_finished_campaigns_take_no_projects(self):
        done = make_campaign(
            slug="done",
            short_code="DON",
            status=CampaignStatus.COMPLETED,
        )
        self.assertEqual(400, self._attach(self.director, done).status_code)

    def test_campaign_page_lists_completed_projects_with_contributors(self):
        self._attach(self.director)
        response = self.client.get(
            f"{CAMPAIGNS}/{self.campaign.slug}/projects",
            **auth_headers(self.outsider),
        )
        self.assertEqual(200, response.status_code)
        [project] = response.json()
        self.assertEqual("Completed", project["state"])
        self.assertEqual("Rattini Tribe", project["corporation_name"])
        self.assertEqual(
            ["Pilot One", "Pilot Two"],
            [row["character_name"] for row in project["contributors"]],
        )

    def test_campaign_projects_follow_campaign_visibility(self):
        stranger = User.objects.create(username="stranger")
        response = self.client.get(
            f"{CAMPAIGNS}/{self.campaign.slug}/projects",
            **auth_headers(stranger),
        )
        self.assertEqual(403, response.status_code)

    def test_detach_by_director_or_campaign_manager(self):
        self._attach(self.director)
        url = f"{CAMPAIGNS}/{self.campaign.slug}/projects/{PROJECT_ID}"
        self.assertEqual(
            403,
            self.client.delete(url, **auth_headers(self.outsider)).status_code,
        )
        manager = User.objects.create(username="manager", is_superuser=True)
        self.assertEqual(
            204, self.client.delete(url, **auth_headers(manager)).status_code
        )
        self.assertFalse(CampaignProject.objects.exists())

    def test_refresh_needs_a_token(self):
        response = self.client.post(
            f"{CORPS}/98000001/projects/refresh",
            **auth_headers(self.director),
        )
        self.assertEqual(409, response.status_code)
