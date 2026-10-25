from unittest.mock import patch

from django.contrib.auth.models import User
from django.db.models import signals
from django.test import Client

from app.test import TestCase
from app.testing import make_token
from eveonline.models import EveCharacter, EveCorporation

BASE_URL = "/api/eveonline/corporations/corporations/98726134"
GET_INVITE = (
    "eveonline.helpers.corporations.discord_invite.DiscordClient.get_invite"
)
INVITE = {
    "code": "rattini",
    "expires_at": None,
    "guild": {"id": "4242", "name": "Rattini Tribe", "icon": "abc123"},
}


class CorporationDiscordEndpointTestCase(TestCase):
    def setUp(self):
        super().setUp()
        for uid in (
            "populate_eve_character_public_data",
            "populate_eve_character_private_data",
        ):
            signals.post_save.disconnect(sender=EveCharacter, dispatch_uid=uid)
        self.client = Client()
        self.ceo = EveCharacter.objects.create(
            character_id=2001, character_name="Ceo", user=self.user
        )
        self.corporation = EveCorporation.objects.create(
            corporation_id=98726134, name="Rattini Tribe", ceo=self.ceo
        )
        self.director_user = User.objects.create(username="director")
        director = EveCharacter.objects.create(
            character_id=2002,
            character_name="Director",
            user=self.director_user,
        )
        self.corporation.directors.add(director)
        self.member_user = User.objects.create(username="member")

    def call(self, method, path="", user=None, body=None):
        token = make_token(user or self.user)
        return getattr(self.client, method)(
            BASE_URL + "/discord" + path,
            data=body,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

    def test_ceo_and_directors_only(self):
        self.assertEqual(200, self.call("get").status_code)
        self.assertEqual(
            200, self.call("get", user=self.director_user).status_code
        )
        self.assertEqual(
            403, self.call("get", user=self.member_user).status_code
        )
        self.assertEqual(
            403,
            self.call(
                "put",
                user=self.member_user,
                body={"invite_url": "discord.gg/x"},
            ).status_code,
        )
        self.assertEqual(
            403, self.call("delete", user=self.member_user).status_code
        )

    @patch(GET_INVITE, return_value=INVITE)
    def test_director_sets_and_removes_the_server(self, mock_get):
        response = self.call(
            "put",
            user=self.director_user,
            body={"invite_url": "https://discord.com/invite/rattini"},
        )
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual("https://discord.gg/rattini", body["invite_url"])
        self.assertEqual("ok", body["status"])
        self.assertEqual("Rattini Tribe", body["guild_name"])

        public = self.client.get(
            "/api/eveonline/corporations/corporations/98726134/info"
        ).json()
        self.assertEqual(
            "https://discord.gg/rattini", public["discord_invite_url"]
        )

        response = self.call("delete", user=self.director_user)
        self.assertEqual(200, response.status_code)
        self.assertFalse(response.json()["exists"])

    @patch(
        GET_INVITE,
        return_value={**INVITE, "expires_at": "2026-11-01T00:00:00Z"},
    )
    def test_put_refuses_expiring_invites(self, mock_get):
        response = self.call("put", body={"invite_url": "discord.gg/rattini"})
        self.assertEqual(400, response.status_code)
        self.assertEqual("invite_expires", response.json()["detail"])
        self.corporation.refresh_from_db()
        self.assertEqual("", self.corporation.discord_invite_url)

    @patch(GET_INVITE, return_value=INVITE)
    def test_check_previews_without_saving(self, mock_get):
        response = self.call(
            "post", path="/check", body={"invite_url": "discord.gg/rattini"}
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {
                "invite_url": "https://discord.gg/rattini",
                "checked": True,
                "guild_name": "Rattini Tribe",
                "icon_url": "https://cdn.discordapp.com/icons/4242/abc123.png?size=64",
            },
            response.json(),
        )
        self.corporation.refresh_from_db()
        self.assertEqual("", self.corporation.discord_invite_url)

    def test_check_rejects_other_links(self):
        response = self.call(
            "post", path="/check", body={"invite_url": "https://example.com"}
        )
        self.assertEqual(400, response.status_code)
        self.assertEqual("not_discord_invite", response.json()["detail"])

    def test_dead_invite_is_not_public(self):
        self.corporation.discord_invite_url = "https://discord.gg/rattini"
        self.corporation.discord_invite_status = (
            EveCorporation.DISCORD_INVITE_DEAD
        )
        self.corporation.save()
        public = self.client.get(
            "/api/eveonline/corporations/corporations/98726134/info"
        ).json()
        self.assertIsNone(public["discord_invite_url"])
        self.assertEqual("dead", self.call("get").json()["status"])

    def test_directors_can_edit_settings(self):
        for user, expected in (
            (self.user, True),
            (self.director_user, True),
            (self.member_user, False),
        ):
            response = self.client.get(
                "/api/eveonline/corporations/corporations/98726134/members/access",
                HTTP_AUTHORIZATION=f"Bearer {make_token(user)}",
            )
            self.assertEqual(
                expected, response.json()["can_edit_settings"], user
            )
