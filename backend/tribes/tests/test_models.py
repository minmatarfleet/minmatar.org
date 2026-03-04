"""Tests for tribes models."""

from django.contrib.auth.models import Group, User
from django.db import IntegrityError
from django.db.models import signals as django_signals
from django.test import TestCase

from eveonline.models import EveCharacter
from tribes.models import (
    Tribe,
    TribeGroup,
    TribeGroupMembership,
    TribeGroupMembershipCharacter,
    TribeGroupMembershipCharacterHistory,
)


def setUpModule():
    """Disconnect the Discord group-change signal that requires a linked DiscordUser."""
    # pylint: disable-next=import-outside-toplevel
    from discord.signals import user_group_changed  # noqa: PLC0415

    django_signals.m2m_changed.disconnect(
        user_group_changed,
        sender=User.groups.through,
        dispatch_uid="user_group_changed",
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
        self.tribe_group = TribeGroup.objects.create(
            tribe=self.tribe, name="Mining"
        )
        self.user = User.objects.create_user(username="miner")

    def test_default_status_is_pending(self):
        m = TribeGroupMembership.objects.create(
            user=self.user, tribe_group=self.tribe_group
        )
        self.assertEqual(m.status, TribeGroupMembership.STATUS_PENDING)

    def test_str(self):
        m = TribeGroupMembership.objects.create(
            user=self.user, tribe_group=self.tribe_group
        )
        self.assertIn("miner", str(m))
        self.assertIn("pending", str(m))

    def test_unique_constraint_blocks_second_row_any_status(self):
        """Exactly one row per (tribe_group, user) regardless of status."""
        TribeGroupMembership.objects.create(
            user=self.user,
            tribe_group=self.tribe_group,
            status=TribeGroupMembership.STATUS_INACTIVE,
        )
        with self.assertRaises(IntegrityError):
            TribeGroupMembership.objects.create(
                user=self.user,
                tribe_group=self.tribe_group,
                status=TribeGroupMembership.STATUS_INACTIVE,
            )

    def test_unique_constraint_blocks_second_active_row(self):
        TribeGroupMembership.objects.create(
            user=self.user,
            tribe_group=self.tribe_group,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        with self.assertRaises(IntegrityError):
            TribeGroupMembership.objects.create(
                user=self.user,
                tribe_group=self.tribe_group,
                status=TribeGroupMembership.STATUS_PENDING,
            )


class TribeGroupMembershipCharacterModelTestCase(TestCase):
    def setUp(self):
        self.tribe = Tribe.objects.create(name="Mining", slug="mining")
        self.tribe_group = TribeGroup.objects.create(
            tribe=self.tribe, name="Mining"
        )
        self.user = User.objects.create_user(username="miner")
        self.membership = TribeGroupMembership.objects.create(
            user=self.user, tribe_group=self.tribe_group
        )
        self.character = EveCharacter.objects.create(
            character_id=12345, character_name="Test Miner", user=self.user
        )

    def test_create_committed_character(self):
        """Adding a character creates a current-roster link."""
        mc = TribeGroupMembershipCharacter.objects.create(
            membership=self.membership, character=self.character
        )
        self.assertEqual(mc.membership, self.membership)
        self.assertEqual(mc.character, self.character)

    def test_remove_character_deletes_link_and_writes_history(self):
        """Removing a character deletes the roster link and appends history."""
        mc = TribeGroupMembershipCharacter.objects.create(
            membership=self.membership, character=self.character
        )
        TribeGroupMembershipCharacterHistory.objects.create(
            membership=self.membership,
            character=self.character,
            action=TribeGroupMembershipCharacterHistory.ACTION_ADDED,
        )
        # Simulate the remove flow.
        TribeGroupMembershipCharacterHistory.objects.create(
            membership=self.membership,
            character=self.character,
            action=TribeGroupMembershipCharacterHistory.ACTION_REMOVED,
            leave_reason=TribeGroupMembershipCharacterHistory.LEAVE_REASON_VOLUNTARY,
        )
        mc.delete()

        self.assertFalse(
            TribeGroupMembershipCharacter.objects.filter(pk=mc.pk).exists()
        )
        self.assertEqual(
            TribeGroupMembershipCharacterHistory.objects.filter(
                membership=self.membership,
                character=self.character,
                action=TribeGroupMembershipCharacterHistory.ACTION_REMOVED,
            ).count(),
            1,
        )

    def test_unique_constraint_prevents_duplicate_current_link(self):
        TribeGroupMembershipCharacter.objects.create(
            membership=self.membership, character=self.character
        )
        with self.assertRaises(IntegrityError):
            TribeGroupMembershipCharacter.objects.create(
                membership=self.membership, character=self.character
            )
