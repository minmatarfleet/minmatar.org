"""Invites on standard fleets: the FC's Invites tab, new pilot lists, the
weekly cap, Stop fleet invites, I'm in with no ship yet and the friendlier
DM (docs/fleets/private-fleets.md)."""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db.models.query import QuerySet
from django.utils import timezone

from alliance.models import AllianceHealthSnapshot
from fleets.helpers.private_fleet_discord import (
    STOP_INVITES_CUSTOM_ID_PREFIX,
    answered_payload,
    invite_payload,
)
from fleets.helpers import private_fleets
from fleets.helpers.private_fleets import (
    OPSEC_LINE,
    PrivateFleetError,
    opted_out_user_ids,
    send_wave,
    stop_fleet_invites,
)
from fleets.models import EveFleet, EveFleetInvite
from fleets.tasks import send_fleet_invite_wave
from fleets.test_private_fleets import VIEW, PrivateFleetTestBase
from tribes.tests.publishing_fixtures import make_user

FC = ("view_evefleet", "add_evefleet")


def _onboarding_snapshot(**pilots_by_bucket):
    """A health snapshot whose trial rows put each user in a bucket:
    first_week = 3 days in, no fleets; more_fleets = 30 days in, 1 fleet."""
    shapes = {"first_week": (3, 0), "more_fleets": (30, 1)}
    rows = []
    for bucket, users in pilots_by_bucket.items():
        days, fleets = shapes[bucket]
        for user in users:
            rows.append(
                {
                    "user_id": user.id,
                    "username": user.username,
                    "pilot": user.username,
                    "corp": "Test Corp",
                    "alliance_days": days,
                    "fleets": fleets,
                    "kills": 0,
                    "kills_small": 0,
                    "voice_hours": 0,
                    "slice_30d": "quiet",
                    "path": "",
                    "conf": "",
                    "reason": "",
                }
            )
    return AllianceHealthSnapshot.objects.create(
        payload={"hygiene": {"trial": {"buckets": {"current": rows}}}}
    )


class StandardInviteTestBase(PrivateFleetTestBase):
    def setUp(self):
        super().setUp()
        self.fc = make_user("fc", perms=FC, character_name="Bear")

    def standard_fleet(self, **fields) -> EveFleet:
        values = {
            "type": "non_strategic",
            "objective": "Sunday Thrasher roam",
            "created_by": self.fc,
            "invite_only": False,
        }
        values.update(fields)
        return self.private_fleet(**values)

    def invite_on(self, fleet, *users, **picks):
        return send_wave(
            fleet,
            sent_by=fleet.created_by,
            user_ids=[u.id for u in users],
            **picks,
        )


class StandardInvitesTabTests(StandardInviteTestBase):
    def test_the_fc_manages_invites_and_others_get_404(self):
        fleet = self.standard_fleet()
        response = self.call("get", f"/{fleet.id}/invites", self.fc)
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertFalse(body["invite_only"])
        self.assertFalse(body["can_see_leak_trace"])
        self.assertEqual(
            self.call("get", f"/{fleet.id}/invites", self.pilot).status_code,
            404,
        )
        # A Strategic FC manages private fleets, not someone else's roam.
        self.assertEqual(
            self.call("get", f"/{fleet.id}/invites", self.strat).status_code,
            404,
        )

    def test_no_reping_on_a_standard_fleet(self):
        # Even for a Strategic FC: re-ping is for private fleets.
        fleet = self.standard_fleet(created_by=self.strat)
        self.invite_on(fleet, self.pilot)
        EveFleetInvite.objects.update(dm_delivered=True)
        body = self.call("get", f"/{fleet.id}/invites", self.strat).json()
        self.assertFalse(body["can_reping"])
        response = self.call("post", f"/{fleet.id}/invites/reping", self.strat)
        self.assertEqual(response.status_code, 403)
        self.assertIsNone(EveFleetInvite.objects.get().reminded_at)

    def test_invited_as_is_kept_per_pilot(self):
        fleet = self.standard_fleet()
        _onboarding_snapshot(first_week=[self.outsider])
        self.invite_on(
            fleet,
            self.pilot,
            tribe_group_ids=[self.group.id],
            onboarding=["first_week"],
        )
        sources = dict(
            EveFleetInvite.objects.filter(eve_fleet=fleet).values_list(
                "user__username", "source_kind"
            )
        )
        self.assertEqual(
            sources,
            {
                "outsider": "first_week",
                "pilot": "pilot",
                "nodiscord": "tribe_group",
            },
        )
        group_invite = EveFleetInvite.objects.get(user=self.no_discord)
        self.assertIn(self.group.name, group_invite.source_name)
        pilots = self.call("get", f"/{fleet.id}/invites", self.fc).json()[
            "invites"
        ]
        self.assertEqual(
            {p["source_kind"] for p in pilots},
            {"first_week", "pilot", "tribe_group"},
        )

    def test_new_pilot_counts_leave_out_who_is_invited(self):
        fleet = self.standard_fleet()
        _onboarding_snapshot(
            first_week=[self.pilot, self.outsider],
            more_fleets=[self.no_discord],
        )
        self.invite_on(fleet, self.pilot)
        body = self.call("get", f"/{fleet.id}/invites", self.fc).json()
        self.assertEqual(body["onboarding_first_week"], 1)
        self.assertEqual(body["onboarding_more_fleets"], 1)

    def test_private_fleets_ignore_new_pilot_picks(self):
        fleet = self.private_fleet()
        _onboarding_snapshot(first_week=[self.pilot])
        preview = self.call(
            "post",
            f"/{fleet.id}/invites/preview",
            self.strat,
            {"onboarding": ["first_week"]},
        ).json()
        self.assertEqual(preview["picked"], 0)


class WeeklyCapTests(StandardInviteTestBase):
    def test_one_standard_invite_a_week(self):
        self.invite_on(self.standard_fleet(), self.pilot)
        fleet = self.standard_fleet()
        preview = self.call(
            "post",
            f"/{fleet.id}/invites/preview",
            self.fc,
            {"user_ids": [self.pilot.id, self.outsider.id]},
        ).json()
        self.assertEqual(preview["capped"], 1)
        self.assertEqual(preview["new"], 1)
        with self.assertRaisesMessage(PrivateFleetError, "this week"):
            self.invite_on(fleet, self.pilot)

    def test_preview_names_who_is_skipped_and_when_they_are_free(self):
        first = self.invite_on(self.standard_fleet(), self.pilot)
        sent = EveFleetInvite.objects.get(wave=first).created_at
        preview = self.call(
            "post",
            f"/{self.standard_fleet().id}/invites/preview",
            self.fc,
            {"user_ids": [self.pilot.id]},
        ).json()
        (row,) = preview["capped_pilots"]
        self.assertEqual(row["user_id"], self.pilot.id)
        self.assertEqual(row["name"], "Teysha")
        self.assertEqual(row["fleet"], "Sunday Thrasher roam")
        self.assertEqual(
            row["free_at"][:16], (sent + timedelta(days=7)).isoformat()[:16]
        )

    def test_old_and_undelivered_invites_dont_count(self):
        old = self.invite_on(self.standard_fleet(), self.pilot)
        EveFleetInvite.objects.filter(wave=old).update(
            created_at=timezone.now() - timedelta(days=8)
        )
        failed = self.invite_on(self.standard_fleet(), self.pilot)
        EveFleetInvite.objects.filter(wave=failed).update(dm_delivered=False)
        self.invite_on(self.standard_fleet(), self.pilot)

    def test_strategic_and_training_invites_count(self):
        for kind in ("strategic", "training"):
            fleet = self.standard_fleet(type=kind)
            self.invite_on(fleet, self.pilot)
            with self.assertRaises(PrivateFleetError):
                self.invite_on(self.standard_fleet(), self.pilot)
            EveFleetInvite.objects.filter(eve_fleet=fleet).delete()

    def test_private_fleets_are_not_limited_and_dont_count(self):
        self.invite_on(self.standard_fleet(), self.pilot)
        # Quiet mode still reaches a pilot who had their invite...
        send_wave(
            self.private_fleet(), sent_by=self.strat, user_ids=[self.pilot.id]
        )
        # ...and its own invite doesn't use up anyone's week.
        send_wave(
            self.private_fleet(),
            sent_by=self.strat,
            user_ids=[self.outsider.id],
        )
        self.invite_on(self.standard_fleet(), self.outsider)

    def test_candidates_say_who_invited_them_this_week(self):
        self.invite_on(self.standard_fleet(), self.pilot)
        fleet = self.standard_fleet(objective="Tuesday frigates")
        (row,) = self.call(
            "get",
            f"/{fleet.id}/invites/candidates?q=teysha&pilots_only=true",
            self.fc,
        ).json()
        self.assertEqual(row["blocked"], "capped")
        self.assertEqual(row["capped"]["fleet"], "Sunday Thrasher roam")
        self.assertIsNotNone(row["capped"]["free_at"])

    def test_pasted_names_say_who_will_be_skipped(self):
        self.invite_on(self.standard_fleet(), self.pilot)
        fleet = self.standard_fleet()
        body = self.call(
            "post",
            f"/{fleet.id}/invites/resolve",
            self.fc,
            {"text": "Teysha"},
        ).json()
        (row,) = body["matched"]
        self.assertEqual(row["blocked"], "capped")
        self.assertEqual(row["capped"]["fleet"], "Sunday Thrasher roam")


class SendLockTests(StandardInviteTestBase):
    """Two FCs sending at once can't both invite one pilot."""

    def _invite_elsewhere_after_preview(self, *users):
        """Another fleet invites ``users`` between this send's preview and
        its write, as a send running at the same moment would."""
        real = private_fleets.wave_preview
        other = self.standard_fleet(objective="Someone else's roam")

        raced = []

        def preview_then_race(*args, **kwargs):
            preview = real(*args, **kwargs)
            if not raced:
                raced.append(True)
                self.invite_on(other, *users)
            return preview

        return patch.object(
            private_fleets, "wave_preview", side_effect=preview_then_race
        )

    def test_send_checks_again_after_locking(self):
        fleet = self.standard_fleet()
        with self._invite_elsewhere_after_preview(self.pilot):
            wave = self.invite_on(fleet, self.pilot, self.outsider)
        self.assertEqual(
            list(
                EveFleetInvite.objects.filter(wave=wave).values_list(
                    "user_id", flat=True
                )
            ),
            [self.outsider.id],
        )

    def test_send_of_only_raced_pilots_is_refused(self):
        fleet = self.standard_fleet()
        with self._invite_elsewhere_after_preview(self.pilot):
            with self.assertRaisesMessage(
                PrivateFleetError, "Someone else just invited them"
            ):
                self.invite_on(fleet, self.pilot)
        self.assertFalse(EveFleetInvite.objects.filter(eve_fleet=fleet))

    def test_send_locks_the_pilots_accounts(self):
        fleet = self.standard_fleet()
        locked = []
        real = QuerySet.select_for_update

        def spy(queryset, *args, **kwargs):
            locked.append(queryset.model)
            return real(queryset, *args, **kwargs)

        with patch.object(QuerySet, "select_for_update", spy):
            self.invite_on(fleet, self.pilot)
        self.assertIn(User, locked)

    def test_private_sends_take_no_lock(self):
        locked = []
        real = QuerySet.select_for_update

        def spy(queryset, *args, **kwargs):
            locked.append(queryset.model)
            return real(queryset, *args, **kwargs)

        with patch.object(QuerySet, "select_for_update", spy):
            send_wave(
                self.private_fleet(),
                sent_by=self.strat,
                user_ids=[self.pilot.id],
            )
        self.assertNotIn(User, locked)


class StopInvitesTests(StandardInviteTestBase):
    def test_discord_button_turns_invites_off(self):
        fleet = self.standard_fleet()
        self.invite_on(fleet, self.pilot)
        invite = EveFleetInvite.objects.get(user=self.pilot)
        response = self.call(
            "post",
            f"/invites/{invite.id}/discord-stop",
            self.pilot,
            {"discord_user_id": 9001},
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(opted_out_user_ids([self.pilot.id]), {self.pilot.id})

        other = self.standard_fleet()
        preview = self.call(
            "post",
            f"/{other.id}/invites/preview",
            self.fc,
            {"user_ids": [self.pilot.id]},
        ).json()
        self.assertEqual(preview["opted_out"], 1)
        self.assertEqual(preview["new"], 0)
        # A private fleet's invite still reaches them.
        send_wave(
            self.private_fleet(), sent_by=self.strat, user_ids=[self.pilot.id]
        )

    def test_someone_else_cannot_stop_your_invites(self):
        fleet = self.standard_fleet()
        self.invite_on(fleet, self.pilot)
        invite = EveFleetInvite.objects.get(user=self.pilot)
        response = self.call(
            "post",
            f"/invites/{invite.id}/discord-stop",
            self.outsider,
            {"discord_user_id": 9002},
        )
        self.assertEqual(response.status_code, 403)

    def test_candidates_say_why_a_pilot_cant_be_invited(self):
        fleet = self.standard_fleet()
        self.invite_on(fleet, self.outsider)
        stop_fleet_invites(self.pilot)
        rows = []
        for q in ("teysha", "outsider"):
            rows += self.call(
                "get",
                f"/{fleet.id}/invites/candidates?q={q}&pilots_only=true",
                self.fc,
            ).json()
        blocked = {row["name"]: row["blocked"] for row in rows}
        self.assertEqual(blocked.get("Teysha"), "opted_out")
        self.assertEqual(blocked.get("outsider pilot"), "invited")
        self.assertTrue(all(row["kind"] == "pilot" for row in rows))


class AnswerTests(StandardInviteTestBase):
    def test_im_in_without_a_ship(self):
        fleet = self.standard_fleet()
        self.invite_on(fleet, self.pilot)
        response = self.call("post", f"/{fleet.id}/invites/me/in", self.pilot)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["answer"], "in")
        detail = self.call("get", f"/{fleet.id}", self.pilot).json()
        self.assertEqual(detail["my_invite_answer"], "in")
        self.assertEqual(detail["my_invite_source"], "pilot")
        self.assertFalse(detail["invite_only"])

    def test_picking_a_ship_says_im_in(self):
        fleet = self.standard_fleet()
        self.invite_on(fleet, self.pilot)
        self.volunteer(fleet, self.pilot)
        self.assertEqual(
            EveFleetInvite.objects.get(user=self.pilot).answer, "in"
        )

    def test_fleet_page_flags_for_the_fc(self):
        fleet = self.standard_fleet()
        detail = self.call("get", f"/{fleet.id}", self.fc).json()
        self.assertTrue(detail["can_manage_invites"])
        self.assertIsNone(detail["my_invite_answer"])


class DmTests(StandardInviteTestBase):
    def test_standard_dm_is_friendly_with_a_stop_button(self):
        fleet = self.standard_fleet()
        _onboarding_snapshot(first_week=[self.pilot])
        self.invite_on(fleet, onboarding=["first_week"])
        invite = EveFleetInvite.objects.get(user=self.pilot)
        payload = invite_payload(invite)
        embed = payload["embeds"][0]
        self.assertEqual(embed["author"]["name"], "Fleets")
        self.assertNotIn(OPSEC_LINE, embed["description"])
        self.assertIn("would like you on this fleet", embed["description"])
        self.assertIn(
            "New to fleets?", [field["name"] for field in embed["fields"]]
        )
        ids = [
            button.get("custom_id", "")
            for button in payload["components"][0]["components"]
        ]
        self.assertTrue(
            any(i.startswith(STOP_INVITES_CUSTOM_ID_PREFIX) for i in ids)
        )
        invite.answer = "in"
        answered = answered_payload(invite)["embeds"][0]
        self.assertNotIn(OPSEC_LINE, answered["description"])
        self.assertIn("No ship yet", answered["description"])

    def test_only_private_dms_have_no_stop_button(self):
        for fleet, has_stop in (
            (self.standard_fleet(type="strategic"), True),
            (self.private_fleet(), False),
        ):
            send_wave(
                fleet, sent_by=fleet.created_by, user_ids=[self.pilot.id]
            )
            invite = EveFleetInvite.objects.get(eve_fleet=fleet)
            ids = [
                button.get("custom_id", "")
                for button in invite_payload(invite)["components"][0][
                    "components"
                ]
            ]
            self.assertEqual(
                any(i.startswith(STOP_INVITES_CUSTOM_ID_PREFIX) for i in ids),
                has_stop,
            )

    def test_sender_dms_a_standard_invite(self):
        fleet = self.standard_fleet()
        wave = self.invite_on(fleet, self.pilot, self.outsider)
        with patch("fleets.tasks.discord_client") as client:
            client.send_dm.return_value.json.return_value = {
                "id": "55",
                "channel_id": "66",
            }
            send_fleet_invite_wave(wave.id)
        self.assertEqual(client.send_dm.call_count, 2)


class CapAcrossUsersTests(StandardInviteTestBase):
    def test_cap_is_per_pilot(self):
        extra = make_user("extra", perms=VIEW)
        self.invite_on(self.standard_fleet(), self.pilot)
        self.invite_on(self.standard_fleet(), extra)
