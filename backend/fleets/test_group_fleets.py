"""Tribe group fleets: create rules, visibility, start ping, schedule,
metrics (docs/tribes/tribe-publishing.md)."""

from datetime import timedelta
from unittest.mock import patch

from django.db.models import signals
from django.test import Client, override_settings
from django.utils import timezone

from app.test import TestCase
from app.testing import make_token
from eveonline.models import EveLocation
from fleets.helpers.metrics import led_fleets
from fleets.models import EveFleet, EveFleetAudience
from fleets.tasks import update_fleet_schedule
from fleets.tests import setup_fleet_reference_data
from tribes.models import TribeGroup
from tribes.tests.publishing_fixtures import (
    GROUP_CHANNEL_ID,
    ROLE_ID,
    TRIBE_CHANNEL_ID,
    add_member,
    make_tribe_group,
    make_user,
)

BASE_URL = "/api/fleets"
VIEW = ("view_evefleet",)
FC_PERMS = ("view_evefleet", "add_evefleet")


def setUpModule():
    signals.post_save.disconnect(
        sender=EveFleet, dispatch_uid="update_fleet_schedule_on_save"
    )


def tearDownModule():
    # pylint: disable-next=import-outside-toplevel
    from fleets.signals import update_fleet_schedule_on_save

    signals.post_save.connect(
        update_fleet_schedule_on_save,
        sender=EveFleet,
        dispatch_uid="update_fleet_schedule_on_save",
    )


class GroupFleetTestBase(TestCase):
    def setUp(self):
        super().setUp()
        setup_fleet_reference_data()
        self.audience = EveFleetAudience.objects.get(name="Test Audience")
        self.audience.discord_channel_id = 4242
        self.audience.save()
        self.group = make_tribe_group(allow_open_fleets=True)
        self.fc = make_user("group_fc", perms=VIEW, character_name="Casper")
        add_member(self.group, self.fc)
        self.member = make_user("member", perms=VIEW)
        add_member(self.group, self.member)
        self.outsider = make_user("outsider", perms=FC_PERMS)
        self.chief = make_user("chief", perms=VIEW)
        self.group.chief = self.chief
        self.group.save()

    def call(self, method, path, user, data=None):
        client = Client()
        kwargs = {"HTTP_AUTHORIZATION": f"Bearer {make_token(user)}"}
        if data is not None:
            kwargs["data"] = data
            kwargs["content_type"] = "application/json"
        return getattr(client, method)(f"{BASE_URL}{path}", **kwargs)

    def group_fleet(self, **fields) -> EveFleet:
        values = {
            "type": "non_strategic",
            "description": "Dread op",
            "start_time": timezone.now() + timedelta(hours=2),
            "created_by": self.fc,
            "host_group": self.group,
            "location": EveLocation.objects.first(),
            "status": "pending",
        }
        values.update(fields)
        return EveFleet.objects.create(**values)

    def alliance_fleet(self, **fields) -> EveFleet:
        values = {
            "type": "training",
            "description": "Alliance op",
            "start_time": timezone.now() + timedelta(hours=1),
            "created_by": self.outsider,
            "audience": self.audience,
            "status": "pending",
        }
        values.update(fields)
        return EveFleet.objects.create(**values)

    def create_payload(self, **fields):
        payload = {
            "type": "non_strategic",
            "description": "Dread op",
            "start_time": (timezone.now() + timedelta(hours=3)).isoformat(),
            "audience_id": self.audience.id,
            "host_group_id": self.group.id,
        }
        payload.update(fields)
        return payload


@patch("fleets.endpoints.helpers.queue_channel_message")
class GroupFleetCreateTests(GroupFleetTestBase):
    def test_member_without_fleets_create_needs_policy(self, queue):
        response = self.call("post", "", self.member, self.create_payload())
        self.assertEqual(response.status_code, 403)

        self.group.fleet_policy = TribeGroup.POLICY_MEMBERS
        self.group.save()
        response = self.call(
            "post", "", self.member, self.create_payload(immediate_ping=True)
        )
        self.assertEqual(response.status_code, 200, response.content)
        fleet = EveFleet.objects.get(id=response.json()["id"])
        self.assertIsNone(fleet.audience)
        self.assertEqual(fleet.host_group, self.group)
        self.assertEqual(response.json()["host_group"]["id"], self.group.id)
        queue.assert_not_called()

    def test_chief_creates_group_fleet_without_pre_ping(self, queue):
        with patch(
            "fleets.helpers.schedule_fleet.send_discord_pre_ping"
        ) as pre_ping:
            response = self.call(
                "post",
                "",
                self.chief,
                self.create_payload(immediate_ping=True, on_schedule=True),
            )
        self.assertEqual(response.status_code, 200, response.content)
        pre_ping.assert_not_called()
        queue.assert_not_called()
        fleet = EveFleet.objects.get(id=response.json()["id"])
        self.assertIsNone(fleet.audience)
        # Not open, so not on the schedule either.
        self.assertFalse(fleet.open_to_alliance)
        self.assertFalse(fleet.on_schedule)

    def test_strategic_group_fleet_is_400(self, queue):
        response = self.call(
            "post", "", self.chief, self.create_payload(type="strategic")
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(EveFleet.objects.exists())

    def test_open_fleet_needs_allow_open_fleets(self, queue):
        self.group.allow_open_fleets = False
        self.group.save()
        response = self.call(
            "post",
            "",
            self.chief,
            self.create_payload(open_to_alliance=True),
        )
        self.assertEqual(response.status_code, 400)

    def test_open_fleet_keeps_on_schedule(self, queue):
        response = self.call(
            "post",
            "",
            self.chief,
            self.create_payload(open_to_alliance=True, on_schedule=True),
        )
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertTrue(body["open_to_alliance"])
        self.assertTrue(body["on_schedule"])

    def test_alliance_fleet_create_unchanged(self, queue):
        payload = self.create_payload()
        del payload["host_group_id"]
        response = self.call("post", "", self.outsider, payload)
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertIsNone(body["host_group"])
        self.assertEqual(body["audience"], "Test Audience")
        # Members without fleets.create still can't make alliance fleets.
        self.assertEqual(
            self.call("post", "", self.member, payload).status_code, 403
        )

    def test_patch_strategic_and_open_rules(self, queue):
        fleet = self.group_fleet()
        response = self.call(
            "patch", f"/{fleet.id}", self.fc, {"type": "strategic"}
        )
        self.assertEqual(response.status_code, 400)
        response = self.call(
            "patch",
            f"/{fleet.id}",
            self.chief,
            {"open_to_alliance": True, "on_schedule": True},
        )
        self.assertEqual(response.status_code, 200, response.content)
        fleet.refresh_from_db()
        self.assertTrue(fleet.open_to_alliance)
        self.assertTrue(fleet.on_schedule)
        self.assertIsNone(fleet.audience)
        # Closing it takes it off the schedule.
        self.call(
            "patch", f"/{fleet.id}", self.fc, {"open_to_alliance": False}
        )
        fleet.refresh_from_db()
        self.assertFalse(fleet.on_schedule)
        # Someone outside the group can't edit it.
        response = self.call(
            "patch", f"/{fleet.id}", self.outsider, {"description": "x"}
        )
        self.assertEqual(response.status_code, 403)


class GroupFleetVisibilityTests(GroupFleetTestBase):
    def ids(self, user, **params):
        query = "&".join(f"{k}={v}" for k, v in params.items())
        response = self.call("get", f"/v3?{query}", user)
        self.assertEqual(response.status_code, 200, response.content)
        return {fleet["id"] for fleet in response.json()}

    def test_members_only_fleet_hidden_from_outsiders(self):
        hidden = self.group_fleet()
        open_fleet = self.group_fleet(open_to_alliance=True)
        alliance = self.alliance_fleet()
        no_audience = self.alliance_fleet(audience=None)

        upcoming = {"fleet_filter": "upcoming"}
        self.assertEqual(
            self.ids(self.outsider, **upcoming), {open_fleet.id, alliance.id}
        )
        for user in (self.member, self.fc, self.chief):
            self.assertEqual(
                self.ids(user, **upcoming),
                {hidden.id, open_fleet.id, alliance.id},
            )
        # An alliance fleet with no audience is still left out, as before.
        self.assertNotIn(no_audience.id, self.ids(self.member, **upcoming))

        superuser = make_user("admin")
        superuser.is_superuser = True
        superuser.save()
        self.assertIn(hidden.id, self.ids(superuser, **upcoming))

    def test_host_group_filter(self):
        hidden = self.group_fleet()
        self.alliance_fleet()
        self.assertEqual(
            self.ids(
                self.member,
                fleet_filter="upcoming",
                host_group_id=self.group.id,
            ),
            {hidden.id},
        )

    def test_creator_who_left_still_sees_their_fleet(self):
        fleet = self.group_fleet()
        self.fc.tribe_memberships.update(status="inactive")
        self.assertIn(fleet.id, self.ids(self.fc, fleet_filter="upcoming"))
        self.assertEqual(
            self.call("get", f"/{fleet.id}", self.fc).status_code, 200
        )

    def test_detail_403_names_the_group(self):
        fleet = self.group_fleet()
        response = self.call("get", f"/{fleet.id}", self.outsider)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {
                "detail": "members_only",
                "host_group": {
                    "id": self.group.id,
                    "code": "capitals.dreads",
                    "name": "Dreads",
                    "tribe_id": self.group.tribe_id,
                    "tribe_name": "Capitals",
                },
            },
        )
        # Other single-fleet endpoints are gated the same way.
        self.assertEqual(
            self.call(
                "get", f"/{fleet.id}/role-volunteers", self.outsider
            ).status_code,
            403,
        )
        response = self.call("get", f"/{fleet.id}", self.member)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["host_group"]["name"], "Dreads")

    def test_open_fleet_detail_visible(self):
        fleet = self.group_fleet(open_to_alliance=True)
        self.assertEqual(
            self.call("get", f"/{fleet.id}", self.outsider).status_code, 200
        )

    def test_alliance_fleet_403_body_unchanged(self):
        fleet = self.alliance_fleet()
        nobody = make_user("nobody")
        response = self.call("get", f"/{fleet.id}", nobody)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.content, b"null")


@patch("fleets.models.queue_channel_message")
class GroupFleetStartPingTests(GroupFleetTestBase):
    def test_group_ping_goes_to_group_channel_with_role(self, queue):
        fleet = self.group_fleet(open_to_alliance=True)
        fleet.notify_discord()
        queue.assert_called_once()
        channel_id = queue.call_args[0][0]
        payload = queue.call_args[1]["payload"]
        self.assertEqual(channel_id, GROUP_CHANNEL_ID)
        self.assertEqual(payload["content"], f"<@&{ROLE_ID}>")
        self.assertNotIn("@everyone", str(payload))
        self.assertIn(
            "**AUDIENCE**: DREADS", payload["embeds"][0]["description"]
        )

    def test_group_ping_falls_back_to_tribe_channel(self, queue):
        self.group.discord_channel_id = None
        self.group.save()
        self.group_fleet().notify_discord()
        self.assertEqual(queue.call_args[0][0], TRIBE_CHANNEL_ID)

    def test_no_channel_no_ping(self, queue):
        self.group.discord_channel_id = None
        self.group.save()
        self.group.tribe.discord_channel_id = None
        self.group.tribe.save()
        self.group_fleet().notify_discord()
        queue.assert_not_called()

    def test_alliance_ping_unchanged(self, queue):
        fleet = self.alliance_fleet()
        fleet.notify_discord()
        self.assertEqual(queue.call_args[0][0], 4242)
        self.assertEqual(queue.call_args[1]["payload"]["content"], "@everyone")

    def test_ping_preview_matches_real_ping(self, queue):
        with patch(
            "tribes.helpers.discord_channels.guild_channels",
            return_value=[
                {"id": GROUP_CHANNEL_ID, "name": "dreads", "type": "text"}
            ],
        ):
            response = self.call(
                "post",
                "/ping-preview",
                self.chief,
                {
                    "type": "non_strategic",
                    "description": "Dread op",
                    "host_group_id": self.group.id,
                },
            )
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body["channel_name"], "dreads")
        self.assertEqual(body["payload"]["content"], f"<@&{ROLE_ID}>")
        # Outsiders can't preview a group's ping.
        response = self.call(
            "post",
            "/ping-preview",
            self.outsider,
            {"type": "non_strategic", "host_group_id": self.group.id},
        )
        self.assertEqual(response.status_code, 403)
        # The alliance preview uses the audience and @everyone.
        response = self.call(
            "post",
            "/ping-preview",
            self.outsider,
            {"type": "training", "audience_id": self.audience.id},
        )
        self.assertEqual(response.json()["payload"]["content"], "@everyone")
        self.assertEqual(response.json()["channel_name"], "TestChannel")


@override_settings(
    WEB_LINK_URL="https://my.minmatar.org", DISCORD_FLEET_EMOJIS={}
)
@patch("fleets.tasks.FLEET_SCHEDULE_CHANNEL_ID", 12345)
@patch("fleets.tasks.discord_client")
class GroupFleetScheduleTests(GroupFleetTestBase):
    def schedule_content(self, discord_client):
        discord_client.get_messages.return_value = []
        discord_client.create_message.reset_mock()
        update_fleet_schedule()
        return discord_client.create_message.call_args[1]["payload"]["content"]

    def test_message_identical_without_tribe_fleets(self, discord_client):
        self.alliance_fleet()
        before = self.schedule_content(discord_client)
        # Members-only, closed or off-schedule group fleets change nothing.
        self.group_fleet()
        self.group_fleet(open_to_alliance=True, on_schedule=False)
        self.group_fleet(on_schedule=True)
        self.assertEqual(self.schedule_content(discord_client), before)
        self.assertNotIn("Tribe fleets", before)

    def test_empty_schedule_identical(self, discord_client):
        before = self.schedule_content(discord_client)
        self.group_fleet()
        self.assertEqual(self.schedule_content(discord_client), before)
        self.assertEqual(
            before,
            "## Fleet Schedule\n- No upcoming fleets, go touch grass you nerd",
        )

    def test_tribe_section(self, discord_client):
        self.alliance_fleet()
        alliance_only = self.schedule_content(discord_client)
        fleet = self.group_fleet(
            open_to_alliance=True, on_schedule=True, objective="Dread op"
        )
        content = self.schedule_content(discord_client)
        self.assertTrue(content.startswith(alliance_only))
        when = fleet.start_time.strftime("%Y-%m-%d %H:%M")
        stamp = int(fleet.start_time.timestamp())
        url = (
            "https://my.minmatar.org/alliance/tribes/"
            f"{self.group.tribe_id}/{self.group.id}/"
        )
        self.assertEqual(
            content[len(alliance_only) :],
            "\n### Tribe fleets\n"
            f"-  {when} EVE (<t:{stamp}>) Casper · [Dreads](<{url}>) "
            "(Capitals) · Dread op\n"
            "-# Open to the alliance: message the FC or apply on the "
            "group's page.",
        )

    def test_tribe_section_stays_under_discord_limit(self, discord_client):
        for _ in range(40):
            self.group_fleet(
                open_to_alliance=True,
                on_schedule=True,
                objective="A long objective " * 4,
            )
        content = self.schedule_content(discord_client)
        self.assertLessEqual(len(content), 2000)
        self.assertRegex(content, r"…and \d+ more\n-# Open to the alliance")


class GroupFleetMetricsTests(GroupFleetTestBase):
    def test_members_only_fleets_not_counted(self):
        alliance = self.alliance_fleet()
        hidden = self.group_fleet()
        open_fleet = self.group_fleet(open_to_alliance=True)
        led = set(led_fleets().values_list("id", flat=True))
        self.assertEqual(led, {alliance.id, open_fleet.id})

        response = self.call("get", "/metrics", self.member)
        ids = {row["fleet_id"] for row in response.json()}
        self.assertNotIn(hidden.id, ids)
        self.assertIn(open_fleet.id, ids)
        self.assertIn(alliance.id, ids)

        response = self.call("get", "/commander-metrics", self.member)
        counts = {
            row["user_id"]: row["fleet_count"] for row in response.json()
        }
        self.assertEqual(counts[self.fc.id], 1)
