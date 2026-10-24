"""Tribe group invitations: chiefs invite, pilots join without review."""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db.models import signals as django_signals
from django.test import Client, TestCase
from django.utils import timezone

from app.testing import make_token
from discord.models import DiscordUser
from eveonline.models import EveCharacter, EvePlayer
from groups.models import UserCommunityStatus
from notifications.models import NotificationChannel, NotificationDelivery
from tribes.helpers.invitation_discord import decline_custom_id
from tribes.helpers.invitations import (
    BLOCK_APPLIED,
    BLOCK_DECLINED,
    BLOCK_INVITED,
    BLOCK_MEMBER,
    BLOCK_TRIAL,
    expire_due_invitations,
    invite_blocker,
)
from tribes.models import (
    Tribe,
    TribeGroup,
    TribeGroupInvitation,
    TribeGroupMembership,
)

BASE_URL = "/api/tribes"


def setUpModule():
    # pylint: disable-next=import-outside-toplevel
    from discord.signals import (  # noqa: PLC0415
        group_post_save,
        user_group_changed,
    )

    django_signals.m2m_changed.disconnect(
        user_group_changed,
        sender=User.groups.through,
        dispatch_uid="user_group_changed",
    )
    django_signals.post_save.disconnect(
        group_post_save,
        sender=Group,
        dispatch_uid="group_post_save",
    )


def _pilot(username, character_id, name, discord_id=None, apply_perm=True):
    user = User.objects.create_user(username=username)
    if apply_perm:
        content_type = ContentType.objects.get(
            app_label="tribes", model="tribegroupmembership"
        )
        user.user_permissions.add(
            Permission.objects.get(
                codename="add_tribegroupmembership",
                content_type=content_type,
            )
        )
    character = EveCharacter.objects.create(
        character_id=character_id, character_name=name, user=user
    )
    EvePlayer.objects.create(
        user=user, primary_character=character, nickname=username
    )
    if discord_id:
        DiscordUser.objects.create(
            id=discord_id, discord_tag=f"{username}#1", user=user
        )
    return user, character


class InvitationTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.tribe = Tribe.objects.create(name="Capitals", slug="caps-inv")
        self.group = TribeGroup.objects.create(
            tribe=self.tribe, name="Dreads", code="capitals.dreads-inv"
        )
        self.chief, _ = _pilot("casper", 91001, "Casper Sullivan", 501)
        self.group.chief = self.chief
        self.group.save()
        self.pilot, self.pilot_char = _pilot(
            "teysha", 91002, "Teysha Blackblade", 502
        )
        self.chief_token = make_token(self.chief)
        self.pilot_token = make_token(self.pilot)
        # Notification workers run eagerly in tests: fake Discord for both
        # the DM send and the answered-DM edit.
        channels_patch = patch("notifications.channels.DiscordClient")
        self.discord_cls = channels_patch.start()
        self.discord_cls.return_value.send_dm.return_value = {
            "id": "9",
            "channel_id": "8",
        }
        self.addCleanup(channels_patch.stop)
        acquire_patch = patch(
            "notifications.channels.acquire", return_value=(True, 0.0)
        )
        acquire_patch.start()
        self.addCleanup(acquire_patch.stop)
        tasks_patch = patch("tribes.tasks.discord")
        self.tasks_discord = tasks_patch.start()
        self.addCleanup(tasks_patch.stop)

    def _group_url(self, suffix=""):
        return (
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.group.pk}"
            f"/invitations{suffix}"
        )

    def _invite(self, user_ids, note="", token=None):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                self._group_url(),
                data={"user_ids": user_ids, "note": note},
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {token or self.chief_token}",
            )

    def _accept(self, invitation_id, character_ids):
        return self.client.post(
            f"{BASE_URL}/invitations/{invitation_id}/accept",
            data={"character_ids": character_ids},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.pilot_token}",
        )

    def test_chief_invites_and_pilot_gets_dm_with_buttons(self):
        response = self._invite([self.pilot.pk], note="Come siege.")
        self.assertEqual(response.status_code, 200, response.content)
        row = response.json()[0]
        self.assertEqual(row["status"], "pending")
        self.assertEqual(row["character_name"], "Teysha Blackblade")
        self.assertEqual(row["invited_by_name"], "Casper Sullivan")

        invitation = TribeGroupInvitation.objects.get()
        self.assertEqual(
            invitation.expires_at.date(),
            (invitation.created_at + timedelta(days=14)).date(),
        )
        delivery = NotificationDelivery.objects.get(
            user=self.pilot,
            notification_type="tribes.invited",
            channel=NotificationChannel.DISCORD,
        )
        payload = delivery.payload
        self.assertIn("Come siege.", payload["discord_embed"]["description"])
        buttons = payload["discord_components"][0]["components"]
        self.assertEqual("Open invite", buttons[0]["label"])
        self.assertTrue(
            buttons[0]["url"].endswith(
                f"/alliance/tribes/{self.tribe.pk}/{self.group.pk}/"
            )
        )
        self.assertEqual(
            decline_custom_id(invitation.pk), buttons[1]["custom_id"]
        )
        self.assertEqual("9", delivery.discord_message_id)

    def test_dm_sends_invite_buttons_not_mark_as_read(self):
        self._invite([self.pilot.pk])
        invitation = TribeGroupInvitation.objects.get()
        sent = self.discord_cls.return_value.send_dm.call_args.kwargs[
            "payload"
        ]
        custom_ids = [
            b.get("custom_id") for b in sent["components"][0]["components"]
        ]
        self.assertIn(decline_custom_id(invitation.pk), custom_ids)
        self.assertFalse(
            any((c or "").startswith("notif_ack:") for c in custom_ids)
        )

    def test_only_managers_can_invite(self):
        outsider, _ = _pilot("outsider", 91003, "Outsider")
        response = self._invite([self.pilot.pk], token=make_token(outsider))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(TribeGroupInvitation.objects.exists())

    def test_cannot_invite_twice(self):
        self._invite([self.pilot.pk])
        response = self._invite([self.pilot.pk])
        self.assertEqual(response.status_code, 400)
        self.assertIn("Teysha Blackblade", response.json()["detail"])
        self.assertEqual(TribeGroupInvitation.objects.count(), 1)

    def test_accept_makes_active_membership_approved_by_inviter(self):
        self._invite([self.pilot.pk])
        invitation = TribeGroupInvitation.objects.get()
        with self.captureOnCommitCallbacks(execute=True):
            response = self._accept(
                invitation.pk, [self.pilot_char.character_id]
            )
        self.assertEqual(response.status_code, 200, response.content)
        membership = TribeGroupMembership.objects.get(
            user=self.pilot, tribe_group=self.group
        )
        self.assertEqual(membership.status, "active")
        self.assertEqual(membership.approved_by, self.chief)
        self.assertEqual(
            [self.pilot_char.pk],
            list(membership.characters.values_list("character_id", flat=True)),
        )
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, "accepted")
        self.assertEqual(invitation.membership, membership)
        answered = NotificationDelivery.objects.get(
            user=self.chief, notification_type="tribes.invite_answered"
        )
        self.assertEqual(
            "Teysha Blackblade joined Dreads", answered.payload["title"]
        )

    def test_accept_rolls_back_when_discord_role_fails(self):
        # pylint: disable-next=import-outside-toplevel
        from discord.exceptions import DiscordRoleAssignmentError

        self._invite([self.pilot.pk])
        invitation = TribeGroupInvitation.objects.get()
        with patch(
            "tribes.models.tribe_group_membership.TribeGroupMembership.save",
            side_effect=DiscordRoleAssignmentError("role add failed"),
        ):
            response = self._accept(
                invitation.pk, [self.pilot_char.character_id]
            )
        self.assertEqual(response.status_code, 502)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, "pending")

    def test_accept_needs_off_trial_when_group_requires_it(self):
        self._invite([self.pilot.pk])
        self.group.require_off_trial = True
        self.group.save()
        UserCommunityStatus.objects.create(
            user=self.pilot, status=UserCommunityStatus.STATUS_TRIAL
        )
        invitation = TribeGroupInvitation.objects.get()
        response = self._accept(invitation.pk, [self.pilot_char.character_id])
        self.assertEqual(response.status_code, 400)
        self.assertFalse(TribeGroupMembership.objects.exists())

    def test_someone_else_cannot_accept(self):
        self._invite([self.pilot.pk])
        invitation = TribeGroupInvitation.objects.get()
        response = self.client.post(
            f"{BASE_URL}/invitations/{invitation.pk}/accept",
            data={"character_ids": [91001]},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.chief_token}",
        )
        self.assertEqual(response.status_code, 404)

    def test_decline_notifies_chief_and_blocks_reinvite(self):
        self._invite([self.pilot.pk])
        invitation = TribeGroupInvitation.objects.get()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"{BASE_URL}/invitations/{invitation.pk}/decline",
                HTTP_AUTHORIZATION=f"Bearer {self.pilot_token}",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "declined")
        self.assertTrue(
            NotificationDelivery.objects.filter(
                user=self.chief, notification_type="tribes.invite_answered"
            ).exists()
        )
        code, detail = invite_blocker(self.pilot, self.group)
        self.assertEqual(code, BLOCK_DECLINED)
        self.assertGreater(detail["until"], timezone.now())
        self.assertEqual(self._invite([self.pilot.pk]).status_code, 400)

    def test_discord_decline_checks_the_clicker(self):
        self._invite([self.pilot.pk])
        invitation = TribeGroupInvitation.objects.get()
        url = f"{BASE_URL}/invitations/{invitation.pk}/discord-decline"
        wrong = self.client.post(
            url,
            data={"discord_user_id": 501},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.pilot_token}",
        )
        self.assertEqual(wrong.status_code, 403)
        right = self.client.post(
            url,
            data={"discord_user_id": 502},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.pilot_token}",
        )
        self.assertEqual(right.status_code, 200)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, "declined")

    def test_withdraw(self):
        self._invite([self.pilot.pk])
        invitation = TribeGroupInvitation.objects.get()
        response = self.client.delete(
            self._group_url(f"/{invitation.pk}"),
            HTTP_AUTHORIZATION=f"Bearer {self.chief_token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "withdrawn")
        self.assertIsNone(invite_blocker(self.pilot, self.group))

    def test_list_and_mine(self):
        self._invite([self.pilot.pk])
        listed = self.client.get(
            self._group_url(),
            HTTP_AUTHORIZATION=f"Bearer {self.chief_token}",
        )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()), 1)
        mine = self.client.get(
            f"{BASE_URL}/invitations/mine",
            HTTP_AUTHORIZATION=f"Bearer {self.pilot_token}",
        )
        self.assertEqual(mine.status_code, 200)
        self.assertEqual(mine.json()[0]["tribe_group_name"], "Dreads")

    def test_candidates_explain_who_cannot_be_invited(self):
        applicant, _ = _pilot("naomi", 91004, "Naomi Skylar")
        membership = TribeGroupMembership.objects.create(
            user=applicant, tribe_group=self.group
        )
        trialist, _ = _pilot("hakkar", 91005, "Hakkar Naskingum")
        self.group.require_off_trial = True
        self.group.save()
        UserCommunityStatus.objects.create(
            user=trialist, status=UserCommunityStatus.STATUS_TRIAL
        )
        response = self.client.get(
            self._group_url("/candidates?q=na"),
            HTTP_AUTHORIZATION=f"Bearer {self.chief_token}",
        )
        self.assertEqual(response.status_code, 200)
        by_name = {r["character_name"]: r for r in response.json()}
        self.assertEqual(by_name["Naomi Skylar"]["blocker"], BLOCK_APPLIED)
        self.assertEqual(
            by_name["Naomi Skylar"]["membership_id"], membership.pk
        )
        self.assertEqual(by_name["Hakkar Naskingum"]["blocker"], BLOCK_TRIAL)

    def test_candidates_need_two_letters(self):
        response = self.client.get(
            self._group_url("/candidates?q=t"),
            HTTP_AUTHORIZATION=f"Bearer {self.chief_token}",
        )
        self.assertEqual(response.json(), [])

    def test_blockers(self):
        self.assertIsNone(invite_blocker(self.pilot, self.group))
        self._invite([self.pilot.pk])
        self.assertEqual(
            invite_blocker(self.pilot, self.group)[0], BLOCK_INVITED
        )
        TribeGroupMembership.objects.create(
            user=self.chief, tribe_group=self.group, status="active"
        )
        self.assertEqual(
            invite_blocker(self.chief, self.group)[0], BLOCK_MEMBER
        )

    def test_expiry(self):
        self._invite([self.pilot.pk])
        invitation = TribeGroupInvitation.objects.get()
        TribeGroupInvitation.objects.filter(pk=invitation.pk).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        response = self._accept(invitation.pk, [self.pilot_char.character_id])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(expire_due_invitations(), 1)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, "expired")
        self.assertIsNone(invite_blocker(self.pilot, self.group))

    def test_answered_dm_is_edited_without_buttons(self):
        self._invite([self.pilot.pk])
        invitation = TribeGroupInvitation.objects.get()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                f"{BASE_URL}/invitations/{invitation.pk}/decline",
                HTTP_AUTHORIZATION=f"Bearer {self.pilot_token}",
            )
        args, kwargs = self.tasks_discord.update_message.call_args
        self.assertEqual(("8", "9"), args)
        self.assertEqual([], kwargs["payload"]["components"])
        self.assertEqual(
            "You declined the invite to Dreads",
            kwargs["payload"]["embeds"][0]["title"],
        )
