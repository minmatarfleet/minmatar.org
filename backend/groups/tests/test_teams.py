from django.test import Client
from django.contrib.auth.models import Group

from app.test import TestCase

from groups.models import Team

BASE_URL = "/api/teams"


class TeamsRouterTestCase(TestCase):
    """Django unit tests for the Teams router"""

    def setUp(self):
        self.client = Client()

        super().setUp()

    def make_team(self, name: str) -> Team:
        group = Group.objects.create(name=name)
        return Team.objects.create(name=name, group=group)

    def test_get_sigs(self):
        team = self.make_team("Test Team")
        team.members.add(self.user)
        self.make_team("Another Team")

        response = self.client.get(f"{BASE_URL}/")

        self.assertEqual(200, response.status_code)
        teams = response.json()
        self.assertEqual(2, len(teams))
        self.assertEqual("Test Team", teams[0]["name"])
        self.assertEqual("Another Team", teams[1]["name"])

        response = self.client.get(
            f"{BASE_URL}/current",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        teams = response.json()
        self.assertEqual(1, len(teams))
        self.assertEqual("Test Team", teams[0]["name"])

        response = self.client.get(f"{BASE_URL}/{team.id}")
        self.assertEqual(200, response.status_code)
        team = response.json()
        self.assertEqual("Test Team", team["name"])