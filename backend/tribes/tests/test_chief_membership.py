"""Tests for syncing tribe chief memberships."""

from django.contrib.auth.models import User
from django.db.models import signals as django_signals
from django.test import TestCase
from django.utils import timezone

from tribes.helpers import user_in_tribe_group
from tribes.helpers.chief_membership import (
    ensure_tribe_chiefs_have_group_memberships,
)
from tribes.models import (
    Tribe,
    TribeGroup,
    TribeGroupMembership,
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


class EnsureTribeChiefsHaveGroupMembershipsTestCase(TestCase):
    def setUp(self):
        self.chief = User.objects.create_user(username="tribe_chief_m")
        self.tribe = Tribe.objects.create(
            name="Capitals",
            slug="capitals",
            chief=self.chief,
        )
        self.tribe_group = TribeGroup.objects.create(
            tribe=self.tribe,
            name="Dreads",
        )

    def test_creates_active_membership_for_chief(self):
        self.assertFalse(
            user_in_tribe_group(self.chief, self.tribe_group),
        )
        n = ensure_tribe_chiefs_have_group_memberships()
        self.assertEqual(n, 1)
        self.assertTrue(
            user_in_tribe_group(self.chief, self.tribe_group),
        )
        m = TribeGroupMembership.objects.get(
            user=self.chief, tribe_group=self.tribe_group
        )
        self.assertEqual(m.status, TribeGroupMembership.STATUS_ACTIVE)
        self.assertEqual(m.approved_by_id, self.chief.pk)

    def test_upgrades_pending_to_active(self):
        TribeGroupMembership.objects.create(
            user=self.chief,
            tribe_group=self.tribe_group,
            status=TribeGroupMembership.STATUS_PENDING,
        )
        n = ensure_tribe_chiefs_have_group_memberships()
        self.assertEqual(n, 1)
        m = TribeGroupMembership.objects.get(
            user=self.chief, tribe_group=self.tribe_group
        )
        self.assertEqual(m.status, TribeGroupMembership.STATUS_ACTIVE)

    def test_reactivates_inactive(self):
        TribeGroupMembership.objects.create(
            user=self.chief,
            tribe_group=self.tribe_group,
            status=TribeGroupMembership.STATUS_INACTIVE,
            left_at=timezone.now(),
        )
        n = ensure_tribe_chiefs_have_group_memberships()
        self.assertEqual(n, 1)
        m = TribeGroupMembership.objects.get(
            user=self.chief, tribe_group=self.tribe_group
        )
        self.assertEqual(m.status, TribeGroupMembership.STATUS_ACTIVE)
        self.assertIsNone(m.left_at)

    def test_skips_inactive_tribe(self):
        self.tribe.is_active = False
        self.tribe.save(update_fields=["is_active"])
        n = ensure_tribe_chiefs_have_group_memberships()
        self.assertEqual(n, 0)
        self.assertFalse(
            TribeGroupMembership.objects.filter(
                user=self.chief, tribe_group=self.tribe_group
            ).exists()
        )

    def test_skips_inactive_tribe_group(self):
        self.tribe_group.is_active = False
        self.tribe_group.save(update_fields=["is_active"])
        n = ensure_tribe_chiefs_have_group_memberships()
        self.assertEqual(n, 0)

    def test_idempotent_when_already_active(self):
        TribeGroupMembership.objects.create(
            user=self.chief,
            tribe_group=self.tribe_group,
            status=TribeGroupMembership.STATUS_ACTIVE,
            approved_by=self.chief,
            approved_at=timezone.now(),
        )
        n = ensure_tribe_chiefs_have_group_memberships()
        self.assertEqual(n, 0)
