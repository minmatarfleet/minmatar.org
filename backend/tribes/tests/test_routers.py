"""Tests for tribes router endpoints."""

import jwt
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import signals as django_signals
from django.test import Client, TestCase

from eveonline.models import EveCharacter
from tribes.models import (
    Tribe,
    TribeGroup,
    TribeGroupActivity,
    TribeGroupMembership,
    TribeGroupMembershipCharacter,
    TribeGroupMembershipCharacterHistory,
)

BASE_URL = "/api/tribes"


def _make_token(user: User) -> str:
    payload = {"user_id": user.pk}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def setUpModule():
    """Disconnect the Discord group-change signal that requires a linked DiscordUser."""
    # pylint: disable-next=import-outside-toplevel
    from discord.signals import user_group_changed  # noqa: PLC0415

    django_signals.m2m_changed.disconnect(
        user_group_changed,
        sender=User.groups.through,
        dispatch_uid="user_group_changed",
    )


class TribesListTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.tribe = Tribe.objects.create(
            name="Capitals", slug="capitals", is_active=True
        )
        self.inactive = Tribe.objects.create(
            name="Old", slug="old", is_active=False
        )

    def test_list_returns_only_active(self):
        response = self.client.get(f"{BASE_URL}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["slug"], "capitals")


class TribeDetailTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.tribe = Tribe.objects.create(name="Capitals", slug="capitals")

    def test_get_existing_tribe(self):
        response = self.client.get(f"{BASE_URL}/{self.tribe.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["slug"], "capitals")

    def test_get_missing_tribe_returns_404(self):
        response = self.client.get(f"{BASE_URL}/99999")
        self.assertEqual(response.status_code, 404)


class TribeGroupsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.tribe = Tribe.objects.create(name="Capitals", slug="capitals")
        self.g1 = TribeGroup.objects.create(
            tribe=self.tribe, name="Dreads", is_active=True
        )
        self.g2 = TribeGroup.objects.create(
            tribe=self.tribe, name="Carriers", is_active=True
        )
        self.inactive = TribeGroup.objects.create(
            tribe=self.tribe, name="Old", is_active=False
        )

    def test_list_groups_returns_active_only(self):
        response = self.client.get(f"{BASE_URL}/{self.tribe.pk}/groups")
        self.assertEqual(response.status_code, 200)
        names = {g["name"] for g in response.json()}
        self.assertIn("Dreads", names)
        self.assertIn("Carriers", names)
        self.assertNotIn("Old", names)


class MembershipApplyTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.tribe = Tribe.objects.create(name="Mining", slug="mining")
        self.tribe_group = TribeGroup.objects.create(
            tribe=self.tribe, name="Mining"
        )
        self.user = User.objects.create_user(username="miner")
        self.token = _make_token(self.user)
        self.character = EveCharacter.objects.create(
            character_id=10001, character_name="Miner One", user=self.user
        )

    def test_apply_creates_pending_membership(self):
        response = self.client.post(
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.tribe_group.pk}/memberships",
            data={"character_ids": [self.character.pk]},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "pending")
        self.assertEqual(data["user_id"], self.user.pk)

    def test_apply_twice_returns_400(self):
        self.client.post(
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.tribe_group.pk}/memberships",
            data={"character_ids": []},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        response = self.client.post(
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.tribe_group.pk}/memberships",
            data={"character_ids": []},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 400)

    def test_apply_requires_auth(self):
        response = self.client.post(
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.tribe_group.pk}/memberships",
            data={"character_ids": []},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_reapply_after_inactive_resets_existing_row(self):
        """Re-applying after going inactive resets the same row to pending."""
        # First application.
        self.client.post(
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.tribe_group.pk}/memberships",
            data={"character_ids": []},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        membership = TribeGroupMembership.objects.get(
            user=self.user, tribe_group=self.tribe_group
        )
        membership.status = TribeGroupMembership.STATUS_INACTIVE
        membership.save()

        # Re-apply.
        response = self.client.post(
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.tribe_group.pk}/memberships",
            data={"character_ids": []},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "pending")
        # Still only one row.
        self.assertEqual(
            TribeGroupMembership.objects.filter(
                user=self.user, tribe_group=self.tribe_group
            ).count(),
            1,
        )


class MembershipApprovalTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.tribe = Tribe.objects.create(name="Mining", slug="mining")
        self.tribe_group = TribeGroup.objects.create(
            tribe=self.tribe, name="Mining"
        )

        self.applicant = User.objects.create_user(username="applicant")
        self.chief = User.objects.create_user(username="chief")
        self.random = User.objects.create_user(username="random")

        self.tribe_group.chief = self.chief
        self.tribe_group.save()

        self.membership = TribeGroupMembership.objects.create(
            user=self.applicant,
            tribe_group=self.tribe_group,
            status=TribeGroupMembership.STATUS_PENDING,
        )

    def test_chief_can_approve(self):
        token = _make_token(self.chief)
        url = f"{BASE_URL}/{self.tribe.pk}/groups/{self.tribe_group.pk}/memberships/{self.membership.pk}/approve"
        response = self.client.post(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, 200)
        self.membership.refresh_from_db()
        self.assertEqual(
            self.membership.status, TribeGroupMembership.STATUS_ACTIVE
        )

    def test_random_user_cannot_approve(self):
        token = _make_token(self.random)
        url = f"{BASE_URL}/{self.tribe.pk}/groups/{self.tribe_group.pk}/memberships/{self.membership.pk}/approve"
        response = self.client.post(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, 403)

    def test_chief_can_deny(self):
        token = _make_token(self.chief)
        url = f"{BASE_URL}/{self.tribe.pk}/groups/{self.tribe_group.pk}/memberships/{self.membership.pk}/deny"
        response = self.client.post(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, 200)
        self.membership.refresh_from_db()
        self.assertEqual(
            self.membership.status, TribeGroupMembership.STATUS_INACTIVE
        )


class MembershipLeaveTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.tribe = Tribe.objects.create(name="Mining", slug="mining")
        self.tribe_group = TribeGroup.objects.create(
            tribe=self.tribe, name="Mining"
        )
        self.user = User.objects.create_user(username="miner")
        self.membership = TribeGroupMembership.objects.create(
            user=self.user,
            tribe_group=self.tribe_group,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )

    def test_user_can_leave_own_membership(self):
        token = _make_token(self.user)
        url = f"{BASE_URL}/{self.tribe.pk}/groups/{self.tribe_group.pk}/memberships/{self.membership.pk}"
        response = self.client.delete(
            url, HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        self.assertEqual(response.status_code, 200)
        self.membership.refresh_from_db()
        self.assertEqual(
            self.membership.status, TribeGroupMembership.STATUS_INACTIVE
        )

    def test_chief_can_remove_member(self):
        chief = User.objects.create_user(username="chief")
        self.tribe_group.chief = chief
        self.tribe_group.save()

        token = _make_token(chief)
        url = f"{BASE_URL}/{self.tribe.pk}/groups/{self.tribe_group.pk}/memberships/{self.membership.pk}"
        response = self.client.delete(
            url, HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        self.assertEqual(response.status_code, 200)
        self.membership.refresh_from_db()
        self.assertEqual(
            self.membership.status, TribeGroupMembership.STATUS_INACTIVE
        )
        self.assertEqual(self.membership.removed_by, chief)


class MembershipCharacterTestCase(TestCase):
    """Tests for committing and removing characters from a membership."""

    def setUp(self):
        self.client = Client()
        self.tribe = Tribe.objects.create(name="Mining", slug="mining")
        self.tribe_group = TribeGroup.objects.create(
            tribe=self.tribe, name="Mining"
        )
        self.user = User.objects.create_user(username="miner")
        self.token = _make_token(self.user)
        self.membership = TribeGroupMembership.objects.create(
            user=self.user,
            tribe_group=self.tribe_group,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        self.character = EveCharacter.objects.create(
            character_id=20001, character_name="Miner Two", user=self.user
        )

    def _add_character(self):
        return self.client.post(
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.tribe_group.pk}"
            f"/memberships/{self.membership.pk}/characters",
            data={"character_id": self.character.character_id},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

    def test_add_character_creates_roster_link_and_history(self):
        response = self._add_character()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            TribeGroupMembershipCharacter.objects.filter(
                membership=self.membership, character=self.character
            ).exists()
        )
        self.assertTrue(
            TribeGroupMembershipCharacterHistory.objects.filter(
                membership=self.membership,
                character=self.character,
                action=TribeGroupMembershipCharacterHistory.ACTION_ADDED,
            ).exists()
        )

    def test_remove_character_deletes_roster_link_and_writes_history(self):
        self._add_character()
        url = (
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.tribe_group.pk}"
            f"/memberships/{self.membership.pk}/characters/{self.character.character_id}"
        )
        response = self.client.delete(
            url, HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            TribeGroupMembershipCharacter.objects.filter(
                membership=self.membership, character=self.character
            ).exists()
        )
        self.assertTrue(
            TribeGroupMembershipCharacterHistory.objects.filter(
                membership=self.membership,
                character=self.character,
                action=TribeGroupMembershipCharacterHistory.ACTION_REMOVED,
            ).exists()
        )

    def test_add_duplicate_character_returns_400(self):
        self._add_character()
        response = self._add_character()
        self.assertEqual(response.status_code, 400)


class CurrentUserTribesTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.tribe = Tribe.objects.create(name="Mining", slug="mining")
        self.tribe_group = TribeGroup.objects.create(
            tribe=self.tribe, name="Mining"
        )
        self.user = User.objects.create_user(username="miner")
        TribeGroupMembership.objects.create(
            user=self.user,
            tribe_group=self.tribe_group,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )

    def test_current_returns_user_tribes(self):
        token = _make_token(self.user)
        response = self.client.get(
            f"{BASE_URL}/current", HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["slug"], "mining")

    def test_current_requires_auth(self):
        response = self.client.get(f"{BASE_URL}/current")
        self.assertEqual(response.status_code, 401)


class TribeGroupActivityDefinitionsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.tribe = Tribe.objects.create(name="Capitals", slug="capitals")
        self.tribe_group = TribeGroup.objects.create(
            tribe=self.tribe, name="Dreads"
        )
        self.member = User.objects.create_user(username="cap_member")
        self.outsider = User.objects.create_user(username="outsider")
        self.chief = User.objects.create_user(username="cap_chief")
        self.tribe.chief = self.chief
        self.tribe.save(update_fields=["chief"])
        TribeGroupMembership.objects.create(
            user=self.member,
            tribe_group=self.tribe_group,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        self.activity = TribeGroupActivity.objects.create(
            tribe_group=self.tribe_group,
            activity_type=TribeGroupActivity.KILLMAIL,
            description="PvP kills",
            is_active=True,
            points_per_record=1.0,
        )
        self.url = f"{BASE_URL}/{self.tribe.pk}/groups/{self.tribe_group.pk}/activities"

    def test_member_can_list_definitions(self):
        token = _make_token(self.member)
        response = self.client.get(
            self.url, HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["items"]), 1)
        item = data["items"][0]
        self.assertEqual(item["id"], self.activity.pk)
        self.assertEqual(item["activity_type"], "killmail")
        self.assertEqual(item["description"], "PvP kills")
        self.assertTrue(item["is_active"])
        self.assertEqual(item["points_per_record"], 1.0)

    def test_tribe_chief_can_list_without_membership(self):
        token = _make_token(self.chief)
        response = self.client.get(
            self.url, HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["items"]), 1)

    def test_non_member_forbidden(self):
        token = _make_token(self.outsider)
        response = self.client.get(
            self.url, HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        self.assertEqual(response.status_code, 403)

    def test_requires_auth(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_wrong_group_returns_404(self):
        token = _make_token(self.member)
        bad_url = f"{BASE_URL}/{self.tribe.pk}/groups/99999/activities"
        response = self.client.get(
            bad_url, HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        self.assertEqual(response.status_code, 404)
