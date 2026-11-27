"""A group's chiefs approve or revoke corporations that follow its fleet
posts (docs/tribes/group-fleet-roundup.md)."""

from django.test import Client

from app.test import TestCase
from app.testing import make_token
from discord.models import DiscordGuild
from eveonline.models import EveCorporation
from tribes.models import TribeGroupChief, TribeGroupCorporationFollow
from tribes.tests.publishing_fixtures import (
    add_member,
    make_tribe_group,
    make_user,
)


class GroupCorporationFollowTests(TestCase):
    def setUp(self):
        super().setUp()
        self.group = make_tribe_group(name="Mining", code="industry.mining")
        self.chief = make_user("chief")
        TribeGroupChief.objects.create(
            tribe_group=self.group, region="US", user=self.chief
        )
        self.member = make_user("member")
        add_member(self.group, self.member)
        corporation = EveCorporation.objects.create(
            corporation_id=98838663,
            name="M-EXC",
            discord_guild=DiscordGuild.objects.create(guild_id=4100, name="M"),
            discord_bot_status=EveCorporation.DISCORD_BOT_OK,
        )
        self.follow = TribeGroupCorporationFollow.objects.create(
            tribe_group=self.group,
            corporation=corporation,
            channel_id=880000111,
            channel_name="mining-pings",
        )

    def call(self, method, path, user, data=None):
        kwargs = {"HTTP_AUTHORIZATION": f"Bearer {make_token(user)}"}
        if data is not None:
            kwargs["data"] = data
            kwargs["content_type"] = "application/json"
        return getattr(Client(), method)(
            f"/api/tribes/groups/{self.group.id}/corporation-follows{path}",
            **kwargs,
        )

    def decide(self, decision, user=None, follow_id=None):
        return self.call(
            "post",
            f"/{follow_id or self.follow.id}",
            user or self.chief,
            {"decision": decision},
        )

    def test_manager_lists_requests(self):
        response = self.call("get", "", self.chief)
        self.assertEqual(response.status_code, 200, response.content)
        row = response.json()[0]
        self.assertEqual(row["follow_id"], self.follow.id)
        self.assertEqual(row["corporation_name"], "M-EXC")
        self.assertEqual(row["channel_name"], "mining-pings")
        self.assertEqual(row["status"], "requested")
        self.assertIsNone(row["decided_by_name"])

    def test_manager_approves(self):
        response = self.decide("approve")
        self.assertEqual(response.status_code, 200, response.content)
        self.follow.refresh_from_db()
        self.assertEqual(self.follow.status, "approved")
        self.assertEqual(self.follow.decided_by, self.chief)
        self.assertIsNotNone(self.follow.decided_at)
        self.assertTrue(self.follow.is_forwarding())
        self.assertEqual(response.json()[0]["decided_by_name"], "chief pilot")

    def test_manager_revokes_approved(self):
        self.decide("approve")
        self.decide("revoke")
        self.follow.refresh_from_db()
        self.assertEqual(self.follow.status, "revoked")
        self.assertFalse(self.follow.is_forwarding())

    def test_revoked_can_be_approved_again(self):
        self.decide("revoke")
        self.decide("approve")
        self.follow.refresh_from_db()
        self.assertEqual(self.follow.status, "approved")

    def test_non_manager_403(self):
        self.assertEqual(self.call("get", "", self.member).status_code, 403)
        self.assertEqual(
            self.decide("approve", user=self.member).status_code, 403
        )
        self.follow.refresh_from_db()
        self.assertEqual(self.follow.status, "requested")

    def test_other_groups_follow_404(self):
        other = make_tribe_group(
            name="Dreads", code="capitals.dreads", role_id=None
        )
        foreign = TribeGroupCorporationFollow.objects.create(
            tribe_group=other,
            corporation=self.follow.corporation,
            channel_id=1,
        )
        self.assertEqual(
            self.decide("approve", follow_id=foreign.id).status_code, 404
        )
        foreign.refresh_from_db()
        self.assertEqual(foreign.status, "requested")

    def test_bad_decision_rejected(self):
        self.assertIn(self.decide("maybe").status_code, (400, 422))
