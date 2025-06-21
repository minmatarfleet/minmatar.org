import factory

from django.db.models import signals
from django.test import Client
from django.contrib.auth.models import Group

from app.test import TestCase
from groups.models import Team, Sig
from groups.helpers import user_in_team


class SigTeamsRouterTestCase(TestCase):
    """Combined tests for Sig and Teams routers"""

    def setUp(self):
        self.client = Client()

        super().setUp()

    def verify(self, item_type, item_name, path):
        self.make_superuser()

        self.make_team_or_sig(item_type, item_name)

        response = self.client.get(
            f"/api/{path}/",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        items = response.json()
        self.assertEqual(1, len(items))

        item_id = items[0]["id"]
        response = self.client.get(
            f"/api/{path}/{item_id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(item_name, response.json()["name"])

        response = self.client.get(
            f"/api/{path}/current",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)

        response = self.client.post(
            f"/api/{path}/{item_id}/requests",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)

        response = self.client.get(
            f"/api/{path}/{item_id}/requests",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(1, len(data))
        self.assertFalse(data[0]["approved"])
        request_id = data[0]["id"]

        response = self.client.post(
            f"/api/{path}/{item_id}/requests/{request_id}/approve",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertTrue(data["approved"])

    def make_team_or_sig(self, item_type, item_name):
        group = Group.objects.create(name=item_name)
        item = item_type.objects.create(name=item_name, group=group)
        item.members.add(self.user)

    @factory.django.mute_signals(signals.m2m_changed, signals.post_save)
    def test_sigs(self):
        self.verify(Sig, "Sig 1", "sigs")

    @factory.django.mute_signals(signals.m2m_changed, signals.post_save)
    def test_teams(self):
        self.verify(Team, "Team 1", "teams")

    @factory.django.mute_signals(signals.m2m_changed, signals.post_save)
    def test_user_in_team(self):
        with self.assertRaises(ValueError):
            self.assertFalse(user_in_team(self.user, "x"))

        self.make_team_or_sig(Team, "Test Team")

        self.assertTrue(user_in_team(self.user, "Test Team"))
