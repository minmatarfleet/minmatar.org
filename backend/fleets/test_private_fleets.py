"""Private (invite-only) fleets: who can see them, waves of invites,
answers, ship targets, the thread start ping and declassifying
(docs/fleets/private-fleets.md)."""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.db.models import signals
from django.test import Client
from django.utils import timezone

from app.test import TestCase
from app.testing import make_token
from discord.models import DiscordUser
from eveonline.models import EveCharacter, EveLocation
from fittings.models import EveFitting
from fleets.helpers.private_fleet_discord import (
    answered_payload,
    invite_payload,
    thread_start_ping_payload,
)
from fleets.helpers.private_fleets import (
    PrivateFleetError,
    reping_no_answers,
    send_wave,
    sit_out,
    target_progress,
)
from fleets.helpers.visibility import alliance_fleets_q
from fleets.models import (
    EveFleet,
    EveFleetAudience,
    EveFleetFitting,
    EveFleetInvite,
    EveFleetShipVolunteer,
)
from fleets.tasks import (
    post_private_fleet_start_ping,
    send_fleet_invite_reminders,
    send_fleet_invite_wave,
    update_fleet_schedule,
)
from fleets.tests import setup_fleet_reference_data
from tribes.tests.publishing_fixtures import (
    add_member,
    make_tribe_group,
    make_user,
)

BASE_URL = "/api/fleets"
VIEW = ("view_evefleet",)
STRAT = ("view_evefleet", "add_evefleet", "manage_any_fleet")


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


class PrivateFleetTestBase(TestCase):
    def setUp(self):
        super().setUp()
        setup_fleet_reference_data()
        self.audience = EveFleetAudience.objects.get(name="Test Audience")
        self.audience.discord_channel_id = 4242
        self.audience.save()
        self.strat = make_user("strat", perms=STRAT, character_name="Casper")
        self.pilot = make_user("pilot", perms=VIEW, character_name="Teysha")
        self.outsider = make_user("outsider", perms=VIEW)
        self.no_discord = make_user("nodiscord", perms=VIEW)
        for index, user in enumerate((self.strat, self.pilot, self.outsider)):
            DiscordUser.objects.create(
                id=9000 + index, discord_tag=user.username, user=user
            )
        self.group = make_tribe_group()
        add_member(self.group, self.pilot)
        add_member(self.group, self.no_discord)

    def call(self, method, path, user, data=None):
        client = Client()
        kwargs = {"HTTP_AUTHORIZATION": f"Bearer {make_token(user)}"}
        if data is not None:
            kwargs["data"] = data
            kwargs["content_type"] = "application/json"
        return getattr(client, method)(f"{BASE_URL}{path}", **kwargs)

    def private_fleet(self, **fields) -> EveFleet:
        values = {
            "type": "strategic",
            "description": "Dread drop",
            "objective": "Saturday dread drop",
            "start_time": timezone.now() + timedelta(hours=20),
            "created_by": self.strat,
            "audience": self.audience,
            "location": EveLocation.objects.first(),
            "status": "pending",
            "invite_only": True,
        }
        values.update(fields)
        return EveFleet.objects.create(**values)

    def invite(self, fleet, *users):
        send_wave(fleet, sent_by=self.strat, user_ids=[u.id for u in users])
        return list(EveFleetInvite.objects.filter(eve_fleet=fleet))

    def volunteer(self, fleet, user, ship_type_id=19720):
        character = EveCharacter.objects.filter(user=user).first()
        return EveFleetShipVolunteer.objects.create(
            eve_fleet=fleet,
            character_id=character.character_id,
            character_name=character.character_name,
            ship_type_id=ship_type_id,
            ship_name="Revelation",
        )


@patch("fleets.endpoints.helpers.queue_channel_message")
class CreatePrivateFleetTests(PrivateFleetTestBase):
    def payload(self, **fields):
        payload = {
            "type": "strategic",
            "description": "Dread drop",
            "start_time": (timezone.now() + timedelta(hours=3)).isoformat(),
            "audience_id": self.audience.id,
            "invite_only": True,
            "immediate_ping": True,
        }
        payload.update(fields)
        return payload

    def test_strategic_fc_creates_without_pre_ping(self, queue):
        response = self.call("post", "", self.strat, self.payload())
        self.assertEqual(response.status_code, 200, response.content)
        fleet = EveFleet.objects.get(id=response.json()["id"])
        self.assertTrue(fleet.invite_only)
        queue.assert_not_called()

    def test_other_fc_cannot(self, queue):
        fc = make_user("fc", perms=("view_evefleet", "add_evefleet"))
        response = self.call("post", "", fc, self.payload())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(EveFleet.objects.exists())

    def test_no_campaign(self, queue):
        response = self.call(
            "post", "", self.strat, self.payload(campaign_id=1)
        )
        self.assertEqual(response.status_code, 400)


class VisibilityTests(PrivateFleetTestBase):
    def test_outsider_gets_404(self):
        fleet = self.private_fleet()
        response = self.call("get", f"/{fleet.id}", self.outsider)
        self.assertEqual(response.status_code, 404)
        response = self.call("get", f"/{fleet.id}/targets", self.outsider)
        self.assertEqual(response.status_code, 404)
        response = self.call("get", f"/{fleet.id}/invites", self.outsider)
        self.assertEqual(response.status_code, 404)

    def test_invitee_sees_it_and_the_view_is_recorded(self):
        fleet = self.private_fleet()
        self.invite(fleet, self.pilot)
        response = self.call("get", f"/{fleet.id}", self.pilot)
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertTrue(body["invite_only"])
        self.assertEqual(body["my_invite_answer"], "pending")
        self.assertFalse(body["can_manage_invites"])
        self.assertIsNone(body["discord_thread_url"])
        invite = EveFleetInvite.objects.get(user=self.pilot)
        self.assertIsNotNone(invite.first_viewed_at)

    def test_strategic_fc_manages_it(self):
        fleet = self.private_fleet(discord_thread_id=77)
        body = self.call("get", f"/{fleet.id}", self.strat).json()
        self.assertTrue(body["can_manage_invites"])
        self.assertTrue(body["discord_thread_url"].endswith("/77"))

    def test_lists_and_schedule_leave_it_out(self):
        fleet = self.private_fleet()
        self.invite(fleet, self.pilot)
        upcoming = "/v3?fleet_filter=upcoming"
        ids = [
            f["id"] for f in self.call("get", upcoming, self.outsider).json()
        ]
        self.assertNotIn(fleet.id, ids)
        # An invitee only sees it listed once they're in.
        ids = [f["id"] for f in self.call("get", upcoming, self.pilot).json()]
        self.assertNotIn(fleet.id, ids)
        self.volunteer(fleet, self.pilot)
        ids = [f["id"] for f in self.call("get", upcoming, self.pilot).json()]
        self.assertIn(fleet.id, ids)
        self.assertFalse(
            EveFleet.objects.filter(alliance_fleets_q(), id=fleet.id).exists()
        )

        with patch("fleets.tasks.discord_client") as client:
            update_fleet_schedule()
        message = str(client.update_message.call_args)
        self.assertNotIn("Strategic", message)

    def test_declassified_fleet_is_public(self):
        fleet = self.private_fleet(
            start_time=timezone.now() - timedelta(hours=3), status="complete"
        )
        response = self.call("post", f"/{fleet.id}/declassify", self.strat)
        self.assertEqual(response.status_code, 200, response.content)
        response = self.call("get", f"/{fleet.id}", self.outsider)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            EveFleet.objects.filter(alliance_fleets_q(), id=fleet.id).exists()
        )

    def test_declassify_waits_for_the_fleet(self):
        fleet = self.private_fleet()
        response = self.call("post", f"/{fleet.id}/declassify", self.strat)
        self.assertEqual(response.status_code, 400)


class WaveTests(PrivateFleetTestBase):
    def test_preview_and_send(self):
        fleet = self.private_fleet()
        body = {
            "tribe_group_ids": [self.group.id],
            "user_ids": [self.strat.id],
        }
        preview = self.call(
            "post", f"/{fleet.id}/invites/preview", self.strat, body
        ).json()
        # The FC isn't invited to their own fleet.
        self.assertEqual(preview["picked"], 3)
        self.assertEqual(preview["new"], 2)
        self.assertEqual(preview["will_dm"], 1)
        self.assertEqual(preview["no_discord"], 1)

        response = self.call(
            "post", f"/{fleet.id}/invites/waves", self.strat, body
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["number"], 1)
        no_dm = EveFleetInvite.objects.get(user=self.no_discord)
        self.assertFalse(no_dm.dm_delivered)

        # Nobody new in the same picks.
        response = self.call(
            "post", f"/{fleet.id}/invites/waves", self.strat, body
        )
        self.assertEqual(response.status_code, 400)

        # A second bulk send waits for the first to finish sending...
        extra = make_user("extra", perms=VIEW)
        bulk = {"user_ids": [self.outsider.id, extra.id]}
        response = self.call(
            "post", f"/{fleet.id}/invites/waves", self.strat, bulk
        )
        self.assertEqual(response.status_code, 409)
        # ...but one pilot can be invited alongside it.
        response = self.call(
            "post",
            f"/{fleet.id}/invites/waves",
            self.strat,
            {"user_ids": [self.outsider.id]},
        )
        self.assertEqual(response.status_code, 201, response.content)

    def test_sender_dms_and_finishes(self):
        fleet = self.private_fleet()
        self.invite(fleet, self.pilot, self.outsider)
        wave = fleet.invite_waves.get()
        with patch("fleets.tasks.discord_client") as client:
            client.send_dm.return_value.json.return_value = {
                "id": "55",
                "channel_id": "66",
            }
            send_fleet_invite_wave(wave.id)
        self.assertEqual(client.send_dm.call_count, 2)
        payload = client.send_dm.call_args.kwargs["payload"]
        self.assertIn("Invite only", payload["embeds"][0]["description"])
        invite = EveFleetInvite.objects.get(user=self.pilot)
        self.assertTrue(invite.dm_delivered)
        self.assertEqual(invite.dm_message_id, 55)
        wave.refresh_from_db()
        self.assertIsNotNone(wave.finished_at)

        # A second wave doesn't message anyone already invited.
        with self.assertRaises(PrivateFleetError):
            send_wave(fleet, sent_by=self.strat, user_ids=[self.pilot.id])

    def test_reping_cooldown(self):
        fleet = self.private_fleet()
        self.invite(fleet, self.pilot)
        EveFleetInvite.objects.update(dm_delivered=True)
        self.assertEqual(reping_no_answers(fleet), 1)
        with self.assertRaises(PrivateFleetError) as error:
            reping_no_answers(fleet)
        self.assertEqual(error.exception.status_code, 429)

    def test_reping_nudges_only_unanswered_pilots(self):
        fleet = self.private_fleet()
        (invite,) = self.invite(fleet, self.pilot)
        EveFleetInvite.objects.update(dm_delivered=True, dm_message_id=55)
        with patch("fleets.tasks.discord_client") as client:
            client.send_dm.return_value.json.return_value = {
                "id": "57",
                "channel_id": "66",
            }
            send_fleet_invite_reminders(fleet.id, [invite.id])
            payload = client.send_dm.call_args.kwargs["payload"]
            embed = payload["embeds"][0]
            self.assertTrue(embed["title"].startswith("Still coming?"))
            self.assertIn("Hit **Sitting out**", embed["description"])
            self.assertNotIn("fields", embed)
            self.assertEqual(payload["message_reference"]["message_id"], "55")
            labels = [
                b["label"] for b in payload["components"][0]["components"]
            ]
            self.assertIn("Sitting out", labels)

            # Answered since the re-ping was queued: no nudge.
            EveFleetInvite.objects.update(answer=EveFleetInvite.ANSWER_OUT)
            send_fleet_invite_reminders(fleet.id, [invite.id])
        self.assertEqual(client.send_dm.call_count, 1)

    def test_invites_tab_leak_trace_for_strategic_fcs_only(self):
        fleet = self.private_fleet(created_by=self.outsider)
        self.invite(fleet, self.pilot)
        self.call("get", f"/{fleet.id}", self.pilot)
        body = self.call("get", f"/{fleet.id}/invites", self.strat).json()
        self.assertTrue(body["can_see_leak_trace"])
        self.assertIsNotNone(body["invites"][0]["first_viewed_at"])
        body = self.call("get", f"/{fleet.id}/invites", self.outsider).json()
        self.assertFalse(body["can_see_leak_trace"])
        self.assertIsNone(body["invites"][0]["first_viewed_at"])

    def test_invites_tab_names_only_alts_next_to_their_hull(self):
        fleet = self.private_fleet()
        self.invite(fleet, self.pilot)
        self.volunteer(fleet, self.pilot)
        alt = EveCharacter.objects.create(
            character_id=990001, character_name="Teysha Alt", user=self.pilot
        )
        EveFleetShipVolunteer.objects.create(
            eve_fleet=fleet,
            character_id=alt.character_id,
            character_name=alt.character_name,
            ship_type_id=19722,
            ship_name="Naglfar",
        )
        body = self.call("get", f"/{fleet.id}/invites", self.strat).json()
        self.assertEqual(
            sorted(body["invites"][0]["ships"]),
            ["Naglfar (Teysha Alt)", "Revelation"],
        )

    def test_resolve_paste_of_characters_and_discord_names(self):
        fleet = self.private_fleet()
        body = {
            "text": "Teysha\npilot\n@nobody-here\nCasper, Teysha",
        }
        response = self.call(
            "post", f"/{fleet.id}/invites/resolve", self.strat, body
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        matched_ids = {row["id"] for row in data["matched"]}
        self.assertEqual(matched_ids, {self.pilot.id, self.strat.id})
        self.assertEqual(data["not_found"], ["nobody-here"])
        by_id = {row["id"]: row for row in data["matched"]}
        self.assertEqual(by_id[self.pilot.id]["kind"], "pilot")
        self.assertEqual(by_id[self.pilot.id]["name"], "Teysha")

    def test_resolve_rejects_a_huge_paste(self):
        fleet = self.private_fleet()
        names = "\n".join(f"Pilot{index}" for index in range(60))
        response = self.call(
            "post",
            f"/{fleet.id}/invites/resolve",
            self.strat,
            {"text": names},
        )
        self.assertEqual(response.status_code, 400)


class AnswerTests(PrivateFleetTestBase):
    def test_picking_a_ship_is_in_and_sitting_out_clears_it(self):
        fleet = self.private_fleet()
        (invite,) = self.invite(fleet, self.pilot)
        self.volunteer(fleet, self.pilot)
        invite.refresh_from_db()
        self.assertEqual(invite.answer, "in")

        response = self.call("post", f"/{fleet.id}/invites/me/out", self.pilot)
        self.assertEqual(response.status_code, 200, response.content)
        invite.refresh_from_db()
        self.assertEqual(invite.answer, "out")
        self.assertFalse(
            EveFleetShipVolunteer.objects.filter(eve_fleet=fleet).exists()
        )

    def test_the_ship_picker_says_im_in(self):
        """The picker saves with bulk_create, which sends no signals."""
        fleet = self.private_fleet()
        (invite,) = self.invite(fleet, self.pilot)
        fitting = EveFitting.objects.create(
            name="Revelation", ship_id=19720, eft_format="[Revelation, x]"
        )
        EveFleetFitting.objects.create(
            eve_fleet=fleet, fitting=fitting, name="Revelation", ship_id=19720
        )
        character = EveCharacter.objects.get(user=self.pilot)
        response = self.call(
            "put",
            f"/{fleet.id}/my-ship-volunteers",
            self.pilot,
            {
                "selections": [
                    {
                        "character_id": character.character_id,
                        "fitting_id": fitting.id,
                    }
                ]
            },
        )
        self.assertEqual(response.status_code, 200, response.content)
        invite.refresh_from_db()
        self.assertEqual(invite.answer, "in")

        # Every fleet route is a 404 for someone not invited, not a 403.
        for path in ("", "/ship-volunteers", "/roles", "/composition"):
            response = self.call("get", f"/{fleet.id}{path}", self.outsider)
            self.assertEqual(response.status_code, 404, path)

    def test_discord_button_must_be_the_invitee(self):
        fleet = self.private_fleet()
        (invite,) = self.invite(fleet, self.pilot)
        response = self.call(
            "post",
            f"/invites/{invite.id}/discord-out",
            self.pilot,
            {"discord_user_id": 9002},
        )
        self.assertEqual(response.status_code, 403)
        response = self.call(
            "post",
            f"/invites/{invite.id}/discord-out",
            self.pilot,
            {"discord_user_id": 9001},
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_no_sitting_out_once_started(self):
        fleet = self.private_fleet()
        (invite,) = self.invite(fleet, self.pilot)
        fleet.status = "active"
        fleet.save()
        invite.refresh_from_db()
        with self.assertRaises(PrivateFleetError):
            sit_out(invite)

    def test_dm_payloads(self):
        fleet = self.private_fleet(discord_thread_id=77)
        (invite,) = self.invite(fleet, self.pilot)
        buttons = invite_payload(invite)["components"][0]["components"]
        self.assertEqual(
            buttons[1]["custom_id"], f"fleet_invite:out:{invite.id}"
        )
        invite.answer = "in"
        labels = [
            b["label"]
            for b in answered_payload(invite)["components"][0]["components"]
        ]
        self.assertIn("Open coordination thread", labels)


class TargetTests(PrivateFleetTestBase):
    def test_targets_count_characters_once_per_line(self):
        fleet = self.private_fleet()
        self.invite(fleet, self.pilot)
        lines = {
            "lines": [
                {"name": "Dreads", "target": 40, "ship_type_ids": [19720]},
                {"name": "TFIs", "target": 40, "ship_type_ids": [17732]},
            ]
        }
        with patch("fleets.tasks.refresh_private_fleet_summary"):
            response = self.call(
                "put", f"/{fleet.id}/targets", self.strat, lines
            )
        self.assertEqual(response.status_code, 200, response.content)
        self.volunteer(fleet, self.pilot)
        rows = {row["name"]: row for row in target_progress(fleet)}
        self.assertEqual(rows["Dreads"]["have"], 1)
        self.assertEqual(rows["Dreads"]["short"], 39)
        self.assertEqual(rows["TFIs"]["have"], 0)

    def test_a_hull_on_one_line_only(self):
        fleet = self.private_fleet()
        lines = {
            "lines": [
                {"name": "Dreads", "target": 40, "ship_type_ids": [19720]},
                {"name": "More", "target": 4, "ship_type_ids": [19720]},
            ]
        }
        response = self.call("put", f"/{fleet.id}/targets", self.strat, lines)
        self.assertEqual(response.status_code, 400)

    def test_pilots_cannot_edit_targets(self):
        fleet = self.private_fleet()
        self.invite(fleet, self.pilot)
        response = self.call(
            "put", f"/{fleet.id}/targets", self.pilot, {"lines": []}
        )
        self.assertEqual(response.status_code, 403)


class StartPingTests(PrivateFleetTestBase):
    def test_start_ping_goes_to_the_thread_not_the_audience(self):
        fleet = self.private_fleet(discord_thread_id=77)
        with patch("fleets.models.queue_channel_message") as channel, patch(
            "discord.outbox.transaction.on_commit", lambda fn: fn()
        ), patch(
            "fleets.tasks.post_private_fleet_start_ping.apply_async"
        ) as ping, patch(
            "fleets.tasks.update_private_fleet_dms.apply_async"
        ):
            fleet.notify_discord()
        channel.assert_not_called()
        ping.assert_called_once()

    def test_thread_ping_only_into_a_private_thread(self):
        fleet = self.private_fleet(discord_thread_id=77)
        with patch("fleets.tasks.discord_client") as client:
            client.get_channel.return_value = {"type": 11}
            post_private_fleet_start_ping(fleet.id)
            client.create_message.assert_not_called()

            client.get_channel.return_value = {"type": 12}
            post_private_fleet_start_ping(fleet.id)
        payload = client.create_message.call_args.kwargs["payload"]
        self.assertEqual(payload["content"], "@everyone")
        self.assertIn(
            "PRIVATE · INVITE ONLY", payload["embeds"][0]["description"]
        )

    def test_payload_rewrites_audience(self):
        payload = thread_start_ping_payload(
            {
                "content": "@everyone",
                "embeds": [{"description": "**TYPE**: X\n**AUDIENCE**: ALL"}],
            }
        )
        self.assertEqual(
            payload["embeds"][0]["description"],
            "**TYPE**: X\n**AUDIENCE**: PRIVATE · INVITE ONLY",
        )
        self.assertEqual(payload["allowed_mentions"], {"parse": ["everyone"]})


class ThreadMemberTests(PrivateFleetTestBase):
    def test_strategic_fcs_are_listed(self):
        # pylint: disable=import-outside-toplevel
        from fleets.helpers.private_fleet_discord import strategic_fc_user_ids

        self.assertEqual(strategic_fc_user_ids(), {self.strat.id})
        self.assertTrue(
            Permission.objects.filter(codename="manage_any_fleet").exists()
        )

    def test_sync_adds_pilot_who_is_in(self):
        # pylint: disable=import-outside-toplevel
        from fleets.tasks import sync_private_fleet_invite

        fleet = self.private_fleet(discord_thread_id=77)
        (invite,) = self.invite(fleet, self.pilot)
        EveFleetInvite.objects.filter(id=invite.id).update(answer="in")
        with patch("fleets.tasks.discord_client") as client, patch(
            "fleets.tasks.refresh_private_fleet_summary"
        ):
            sync_private_fleet_invite(invite.id)
        client.add_thread_member.assert_called_once_with(77, 9001)
        invite.refresh_from_db()
        self.assertTrue(invite.in_thread)
