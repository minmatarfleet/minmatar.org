"""Tests for tribes models."""

from django.contrib.auth.models import Group, User
from django.db import IntegrityError
from django.db.models import signals as django_signals
from django.test import TestCase
from django.utils import timezone

from eveonline.models import EveCharacter
from tribes.models import (
    Tribe,
    TribeActivity,
    TribeGroup,
    TribeGroupMembership,
    TribeGroupMembershipCharacter,
)


def setUpModule():
    """Disconnect the Discord group-change signal that requires a linked DiscordUser."""
    # pylint: disable-next=import-outside-toplevel
    from discord.signals import user_group_changed  # noqa: PLC0415

    django_signals.m2m_changed.disconnect(
        user_group_changed, sender=User.groups.through, dispatch_uid="user_group_changed"
    )


class TribeModelTestCase(TestCase):
    def setUp(self):
        self.auth_group = Group.objects.create(name="Test Tribe Group")
        self.chief = User.objects.create_user(username="chief")
        self.tribe = Tribe.objects.create(
            name="Capitals",
            slug="capitals",
            description="Capital ship pilots",
            group=self.auth_group,
            chief=self.chief,
        )

    def test_str(self):
        self.assertEqual(str(self.tribe), "Capitals")

    def test_is_active_default(self):
        self.assertTrue(self.tribe.is_active)

    def test_slug_unique(self):
        with self.assertRaises(IntegrityError):
            Tribe.objects.create(name="Other", slug="capitals")


class TribeGroupModelTestCase(TestCase):
    def setUp(self):
        self.tribe = Tribe.objects.create(name="Capitals", slug="capitals")
        self.tribe_group_auth = Group.objects.create(name="Dreads")
        self.chief = User.objects.create_user(username="chief")
        self.elder = User.objects.create_user(username="elder")
        self.group = TribeGroup.objects.create(
            tribe=self.tribe,
            name="Dreads",
            description="Dreadnought pilots",
            group=self.tribe_group_auth,
            chief=self.chief,
            ship_type_ids=[19720, 19726],
        )
        self.group.elders.add(self.elder)

    def test_str(self):
        self.assertEqual(str(self.group), "Capitals — Dreads")

    def test_elders_m2m(self):
        self.assertIn(self.elder, self.group.elders.all())

    def test_unique_together_tribe_name(self):
        with self.assertRaises(IntegrityError):
            TribeGroup.objects.create(tribe=self.tribe, name="Dreads")


class TribeGroupMembershipModelTestCase(TestCase):
    def setUp(self):
        self.tribe = Tribe.objects.create(name="Mining", slug="mining")
        self.tribe_group = TribeGroup.objects.create(tribe=self.tribe, name="Mining")
        self.user = User.objects.create_user(username="miner")

    def test_default_status_is_pending(self):
        m = TribeGroupMembership.objects.create(user=self.user, tribe_group=self.tribe_group)
        self.assertEqual(m.status, TribeGroupMembership.STATUS_PENDING)

    def test_str(self):
        m = TribeGroupMembership.objects.create(user=self.user, tribe_group=self.tribe_group)
        self.assertIn("miner", str(m))
        self.assertIn("pending", str(m))

    def test_unique_active_constraint_allows_multiple_inactive(self):
        """Multiple non-approved memberships (e.g. historical) should be allowed."""
        TribeGroupMembership.objects.create(
            user=self.user, tribe_group=self.tribe_group, status=TribeGroupMembership.STATUS_LEFT
        )
        TribeGroupMembership.objects.create(
            user=self.user, tribe_group=self.tribe_group, status=TribeGroupMembership.STATUS_LEFT
        )

    def test_unique_active_constraint_blocks_two_approved(self):
        TribeGroupMembership.objects.create(
            user=self.user,
            tribe_group=self.tribe_group,
            status=TribeGroupMembership.STATUS_APPROVED,
        )
        with self.assertRaises(IntegrityError):
            TribeGroupMembership.objects.create(
                user=self.user,
                tribe_group=self.tribe_group,
                status=TribeGroupMembership.STATUS_APPROVED,
            )


class TribeGroupMembershipCharacterModelTestCase(TestCase):
    def setUp(self):
        self.tribe = Tribe.objects.create(name="Mining", slug="mining")
        self.tribe_group = TribeGroup.objects.create(tribe=self.tribe, name="Mining")
        self.user = User.objects.create_user(username="miner")
        self.membership = TribeGroupMembership.objects.create(
            user=self.user, tribe_group=self.tribe_group
        )
        self.character = EveCharacter.objects.create(
            character_id=12345, character_name="Test Miner", user=self.user
        )

    def test_create_committed_character(self):
        mc = TribeGroupMembershipCharacter.objects.create(
            membership=self.membership, character=self.character
        )
        self.assertEqual(mc.membership, self.membership)
        self.assertEqual(mc.character, self.character)
        self.assertIsNone(mc.left_at)

    def test_soft_delete(self):
        mc = TribeGroupMembershipCharacter.objects.create(
            membership=self.membership, character=self.character
        )
        mc.left_at = timezone.now()
        mc.leave_reason = TribeGroupMembershipCharacter.LEAVE_REASON_VOLUNTARY
        mc.save()
        self.assertIsNotNone(mc.left_at)
        self.assertEqual(mc.leave_reason, "voluntary")


class TribeActivityModelTestCase(TestCase):
    def setUp(self):
        self.tribe = Tribe.objects.create(name="Capitals", slug="capitals")
        self.tribe_group = TribeGroup.objects.create(tribe=self.tribe, name="Dreads")
        self.user = User.objects.create_user(username="pilot")

    def test_create_activity(self):
        a = TribeActivity.objects.create(
            tribe_group=self.tribe_group,
            user=self.user,
            activity_type=TribeActivity.ACTIVITY_KILLS,
            quantity=1.0,
            unit="kills",
            reference_type="EveCharacterKillmailAttacker",
            reference_id="99999:12345",
        )
        self.assertEqual(a.quantity, 1.0)
        self.assertEqual(a.unit, "kills")

    def test_unique_reference_constraint(self):
        TribeActivity.objects.create(
            tribe_group=self.tribe_group,
            user=self.user,
            activity_type=TribeActivity.ACTIVITY_KILLS,
            quantity=1.0,
            unit="kills",
            reference_type="EveCharacterKillmailAttacker",
            reference_id="99999:12345",
        )
        with self.assertRaises(IntegrityError):
            TribeActivity.objects.create(
                tribe_group=self.tribe_group,
                user=self.user,
                activity_type=TribeActivity.ACTIVITY_KILLS,
                quantity=1.0,
                unit="kills",
                reference_type="EveCharacterKillmailAttacker",
                reference_id="99999:12345",
            )

    def test_empty_reference_id_not_constrained(self):
        """Two activities with empty reference_id should be allowed (manual logs)."""
        TribeActivity.objects.create(
            tribe_group=self.tribe_group,
            user=self.user,
            activity_type=TribeActivity.ACTIVITY_CUSTOM,
            quantity=1.0,
            unit="tickets",
            reference_type="manual",
            reference_id="",
        )
        TribeActivity.objects.create(
            tribe_group=self.tribe_group,
            user=self.user,
            activity_type=TribeActivity.ACTIVITY_CUSTOM,
            quantity=1.0,
            unit="tickets",
            reference_type="manual",
            reference_id="",
        )
        self.assertEqual(TribeActivity.objects.count(), 2)
