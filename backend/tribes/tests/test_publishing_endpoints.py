"""Tribe publishing endpoints: group flags, settings, pickers."""

from unittest.mock import patch

from django.core.cache import cache
from django.test import Client

from app.test import TestCase
from app.testing import make_token
from tribes.models import TribeGroup
from tribes.tests.publishing_fixtures import (
    GROUP_CHANNEL_ID,
    TRIBE_CHANNEL_ID,
    add_member,
    make_tribe_group,
    make_user,
)

BASE_URL = "/api/tribes"
CHANNELS = [
    {"id": GROUP_CHANNEL_ID, "name": "dreads", "type": "text"},
    {"id": TRIBE_CHANNEL_ID, "name": "capitals", "type": "text"},
    {"id": 9001, "name": "Fleet Comms", "type": "voice"},
    {"id": 9002, "name": "Town Hall", "type": "stage"},
    {"id": 9003, "name": "Tribes", "type": "category"},
]


def character_id(user):
    return user.eveplayer.primary_character.character_id


class PublishingEndpointTests(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.group = make_tribe_group()
        self.member = make_user("member")
        add_member(self.group, self.member)
        self.chief = make_user("chief")
        self.group.chief = self.chief
        self.group.save()
        self.outsider = make_user("outsider")

    def call(self, method, path, user=None, data=None):
        kwargs = {}
        if user is not None:
            kwargs["HTTP_AUTHORIZATION"] = f"Bearer {make_token(user)}"
        if data is not None:
            kwargs["data"] = data
            kwargs["content_type"] = "application/json"
        return getattr(Client(), method)(f"{BASE_URL}{path}", **kwargs)

    def group_path(self):
        return f"/{self.group.tribe_id}/groups/{self.group.id}"

    def test_group_detail_flags(self):
        anonymous = self.call("get", self.group_path()).json()
        self.assertFalse(anonymous["is_member"])
        self.assertFalse(anonymous["can_post"])
        self.assertEqual(
            anonymous["discord_role_name"], "Tribe Group - Dreads"
        )
        self.assertEqual(
            anonymous["effective_discord_channel_id"], str(GROUP_CHANNEL_ID)
        )
        self.assertTrue(anonymous["allow_alliance_posts"])
        self.assertFalse(anonymous["allow_open_fleets"])

        member = self.call("get", self.group_path(), self.member).json()
        self.assertTrue(member["is_member"])
        self.assertFalse(member["can_post"])

        self.group.event_policy = TribeGroup.POLICY_MEMBERS
        self.group.save()
        rows = self.call(
            "get", f"/{self.group.tribe_id}/groups", self.member
        ).json()
        self.assertTrue(rows[0]["is_member"])
        self.assertTrue(rows[0]["can_create_events"])
        self.assertFalse(rows[0]["can_schedule_fleets"])

        chief = self.call("get", self.group_path(), self.chief).json()
        self.assertTrue(chief["can_post"])
        self.assertTrue(chief["can_schedule_fleets"])
        self.assertTrue(chief["can_create_events"])

    @patch(
        "tribes.helpers.discord_channels.guild_channels", return_value=CHANNELS
    )
    def test_publishing_get_and_patch(self, channels):
        path = f"/groups/{self.group.id}/publishing"
        self.assertEqual(self.call("get", path, self.member).status_code, 403)
        self.assertEqual(
            self.call("patch", path, self.member, {}).status_code, 403
        )
        self.assertEqual(
            self.call(
                "get", "/groups/999999/publishing", self.chief
            ).status_code,
            404,
        )

        body = self.call("get", path, self.chief).json()
        self.assertEqual(body["post_policy"], "chiefs")
        self.assertEqual(body["effective_discord_channel_name"], "dreads")
        self.assertEqual(body["discord_role_name"], "Tribe Group - Dreads")

        response = self.call(
            "patch",
            path,
            self.chief,
            {"fleet_publisher_character_ids": [character_id(self.outsider)]},
        )
        self.assertEqual(response.status_code, 400)

        response = self.call(
            "patch",
            path,
            self.chief,
            {
                "fleet_policy": "chosen",
                "fleet_publisher_character_ids": [character_id(self.member)],
                "allow_open_fleets": True,
                "discord_channel_id": None,
            },
        )
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body["fleet_policy"], "chosen")
        self.assertEqual(
            [p["character_id"] for p in body["fleet_publishers"]],
            [character_id(self.member)],
        )
        self.assertTrue(body["allow_open_fleets"])
        self.assertIsNone(body["discord_channel_id"])
        self.assertEqual(
            body["effective_discord_channel_id"], str(TRIBE_CHANNEL_ID)
        )
        self.assertEqual(body["effective_discord_channel_name"], "capitals")
        # Untouched fields stay put.
        self.assertEqual(body["post_policy"], "chiefs")

        response = self.call(
            "patch", path, self.chief, {"discord_channel_id": "9001"}
        )
        self.assertEqual(response.status_code, 400)

    def test_publishable_groups(self):
        self.group.fleet_policy = TribeGroup.POLICY_MEMBERS
        self.group.save()
        rows = self.call(
            "get", "/publishable-groups?kind=fleet", self.member
        ).json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], self.group.id)
        self.assertEqual(rows[0]["member_count"], 1)
        self.assertEqual(rows[0]["tribe_name"], "Capitals")
        self.assertEqual(
            self.call(
                "get", "/publishable-groups?kind=post", self.member
            ).json(),
            [],
        )

    @patch("tribes.helpers.discord_channels.DiscordClient")
    def test_discord_channels(self, client):
        client.return_value.get_guild_channels.return_value = CHANNELS
        self.assertEqual(
            self.call(
                "get", "/discord-channels?kind=voice", self.member
            ).status_code,
            403,
        )
        voice = self.call("get", "/discord-channels?kind=voice", self.chief)
        self.assertEqual(
            [c["name"] for c in voice.json()], ["Fleet Comms", "Town Hall"]
        )
        text = self.call("get", "/discord-channels?kind=text", self.chief)
        self.assertEqual(
            [c["name"] for c in text.json()], ["capitals", "dreads"]
        )
        # Cached: Discord was asked once.
        self.assertEqual(client.return_value.get_guild_channels.call_count, 1)
