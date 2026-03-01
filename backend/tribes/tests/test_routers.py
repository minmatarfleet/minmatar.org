"""Tests for tribes router endpoints."""

import jwt
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import signals as django_signals
from django.test import Client, TestCase

from eveonline.models import EveCharacter
from tribes.models import (
    Tribe,
    TribeActivity,
    TribeGroup,
    TribeGroupMembership,
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
            self.membership.status, TribeGroupMembership.STATUS_APPROVED
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
            self.membership.status, TribeGroupMembership.STATUS_DENIED
        )

    def test_elder_can_approve(self):
        elder = User.objects.create_user(username="elder")
        self.tribe_group.elders.add(elder)
        token = _make_token(elder)
        url = f"{BASE_URL}/{self.tribe.pk}/groups/{self.tribe_group.pk}/memberships/{self.membership.pk}/approve"
        response = self.client.post(url, HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(response.status_code, 200)


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
            status=TribeGroupMembership.STATUS_APPROVED,
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
            self.membership.status, TribeGroupMembership.STATUS_LEFT
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
            self.membership.status, TribeGroupMembership.STATUS_REMOVED
        )
        self.assertEqual(self.membership.removed_by, chief)


class OutputEndpointsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.tribe = Tribe.objects.create(name="Dreads Tribe", slug="dreads")
        self.tribe_group = TribeGroup.objects.create(
            tribe=self.tribe, name="Dreads"
        )
        self.user = User.objects.create_user(username="pilot")

        TribeActivity.objects.create(
            tribe_group=self.tribe_group,
            user=self.user,
            activity_type=TribeActivity.ACTIVITY_KILLS,
            quantity=3.0,
            unit="kills",
            reference_type="test",
            reference_id="ref1",
        )
        TribeActivity.objects.create(
            tribe_group=self.tribe_group,
            user=self.user,
            activity_type=TribeActivity.ACTIVITY_KILLS,
            quantity=2.0,
            unit="kills",
            reference_type="test",
            reference_id="ref2",
        )

    def test_tribe_output_aggregates(self):
        response = self.client.get(f"{BASE_URL}/{self.tribe.pk}/output")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # New shape: list of GroupOutputSummarySchema (one per group).
        self.assertIsInstance(data, list)
        group_summary = next(
            (r for r in data if r["tribe_group_id"] == self.tribe_group.pk),
            None,
        )
        self.assertIsNotNone(group_summary)
        kills_total = group_summary["totals"].get("kills (kills)")
        self.assertEqual(kills_total, 5.0)

    def test_group_output_aggregates(self):
        response = self.client.get(
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.tribe_group.pk}/output"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # New shape: single GroupOutputSummarySchema with totals dict.
        kills_total = data["totals"].get("kills (kills)")
        self.assertEqual(kills_total, 5.0)

    def test_leaderboard(self):
        token = _make_token(self.user)
        response = self.client.get(
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.tribe_group.pk}/leaderboard?activity_type=kills",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        # New schema uses "total" instead of "total_quantity".
        self.assertEqual(data[0]["total"], 5.0)


class LogActivityTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.tribe = Tribe.objects.create(name="Conversion", slug="conversion")
        self.tribe_group = TribeGroup.objects.create(
            tribe=self.tribe, name="Conversion"
        )
        self.chief = User.objects.create_user(username="chief")
        self.tribe_group.chief = self.chief
        self.tribe_group.save()
        self.target_user = User.objects.create_user(username="converter")

    def test_chief_can_log_activity(self):
        token = _make_token(self.chief)
        response = self.client.post(
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.tribe_group.pk}/activities",
            data={
                "activity_type": "custom",
                "user_id": self.target_user.pk,
                "quantity": 1000000.0,
                "unit": "ISK",
                "description": "LP conversion",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["quantity"], 1000000.0)

    def test_regular_user_cannot_log_activity(self):
        regular = User.objects.create_user(username="regular")
        token = _make_token(regular)
        response = self.client.post(
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.tribe_group.pk}/activities",
            data={
                "activity_type": "custom",
                "user_id": self.target_user.pk,
                "quantity": 1.0,
                "unit": "ISK",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 403)


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
            status=TribeGroupMembership.STATUS_APPROVED,
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
