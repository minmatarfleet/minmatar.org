"""Tests for tribes signals."""

from django.contrib.auth.models import Group, User
from django.db.models import signals as django_signals
from django.test import TestCase
from django.utils import timezone

from tribes.helpers.tribe_auth_groups import (
    remove_tribe_auth_groups_for_inactive_membership,
)
from tribes.models import (
    Tribe,
    TribeGroup,
    TribeGroupMembership,
    TribeGroupMembershipHistory,
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


class MembershipSignalTestCase(TestCase):
    def setUp(self):
        self.tribe_auth_group = Group.objects.create(name="Tribe Auth Group")
        self.group_auth_group = Group.objects.create(name="Group Auth Group")
        self.tribe = Tribe.objects.create(
            name="Capitals",
            slug="capitals",
            group=self.tribe_auth_group,
        )
        self.tribe_group = TribeGroup.objects.create(
            tribe=self.tribe,
            name="Dreads",
            group=self.group_auth_group,
        )
        self.user = User.objects.create_user(username="pilot")

    def test_active_adds_user_to_group_auth_groups(self):
        membership = TribeGroupMembership.objects.create(
            user=self.user, tribe_group=self.tribe_group
        )
        membership.status = TribeGroupMembership.STATUS_ACTIVE
        membership.save()

        self.assertIn(self.group_auth_group, self.user.groups.all())
        self.assertIn(self.tribe_auth_group, self.user.groups.all())

    def test_active_appends_membership_history(self):
        membership = TribeGroupMembership.objects.create(
            user=self.user, tribe_group=self.tribe_group
        )
        membership.status = TribeGroupMembership.STATUS_ACTIVE
        membership.save()

        history = TribeGroupMembershipHistory.objects.filter(
            membership=membership, to_status=TribeGroupMembership.STATUS_ACTIVE
        )
        self.assertTrue(history.exists())

    def test_inactive_removes_user_from_group_auth_group(self):
        membership = TribeGroupMembership.objects.create(
            user=self.user,
            tribe_group=self.tribe_group,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        # Manually add user (signal fires on save above)
        self.user.groups.add(self.group_auth_group)
        self.user.groups.add(self.tribe_auth_group)

        membership.status = TribeGroupMembership.STATUS_INACTIVE
        membership.left_at = timezone.now()
        membership.history_inactive_reason = "left"
        membership.save()

        self.assertNotIn(self.group_auth_group, self.user.groups.all())
        self.assertNotIn(self.tribe_auth_group, self.user.groups.all())

    def test_inactive_leaves_tribe_group_if_other_active_membership_exists(
        self,
    ):
        """User stays in tribe auth group if they still have another active TribeGroup in the tribe."""
        group2_auth = Group.objects.create(name="Carriers Auth Group")
        tribe_group2 = TribeGroup.objects.create(
            tribe=self.tribe, name="Carriers", group=group2_auth
        )

        m1 = TribeGroupMembership.objects.create(
            user=self.user,
            tribe_group=self.tribe_group,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        TribeGroupMembership.objects.create(
            user=self.user,
            tribe_group=tribe_group2,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        self.user.groups.add(self.tribe_auth_group)
        self.user.groups.add(self.group_auth_group)

        # Go inactive in first group — tribe auth group should remain because of m2.
        m1.status = TribeGroupMembership.STATUS_INACTIVE
        m1.left_at = timezone.now()
        m1.history_inactive_reason = "removed"
        m1.save()

        self.assertNotIn(self.group_auth_group, self.user.groups.all())
        self.assertIn(self.tribe_auth_group, self.user.groups.all())

    def test_inactive_membership_stale_auth_groups_removed_by_helper(self):
        """Inactive row with auth groups still attached (e.g. missed signal) is fixed."""
        membership = TribeGroupMembership.objects.create(
            user=self.user,
            tribe_group=self.tribe_group,
            status=TribeGroupMembership.STATUS_INACTIVE,
        )
        self.user.groups.add(self.group_auth_group, self.tribe_auth_group)

        remove_tribe_auth_groups_for_inactive_membership(membership)

        self.assertNotIn(self.group_auth_group, self.user.groups.all())
        self.assertNotIn(self.tribe_auth_group, self.user.groups.all())
