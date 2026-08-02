"""Tests for tribes signals."""

from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.db.models import signals as django_signals
from django.test import TestCase
from django.db import transaction
from django.utils import timezone

from discord.exceptions import DiscordRoleAssignmentError
from discord.models import DiscordRole, DiscordUser
from discord.signals import group_post_save, user_group_changed
from tribes.helpers.tribe_auth_groups import (
    remove_tribe_auth_groups_for_inactive_membership,
)
from tribes.models import (
    Tribe,
    TribeGroup,
    TribeGroupMembership,
    TribeGroupMembershipHistory,
    TribeGroupRank,
)


def setUpModule():
    """Disconnect Discord signals that hit the live API during tests."""
    django_signals.post_save.disconnect(
        group_post_save,
        sender=Group,
        dispatch_uid="group_post_save",
    )
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


class MembershipRankSignalTestCase(TestCase):
    def setUp(self):
        self.tribe = Tribe.objects.create(name="Pulse", slug="pulse")
        self.tribe_group = TribeGroup.objects.create(
            tribe=self.tribe,
            name="Fleet Commanders",
            code="pulse.fleet-commanders",
        )
        self.strategic_group = Group.objects.create(name="Strategic FC")
        self.skirmish_group = Group.objects.create(name="Skirmish FC")
        self.strategic_rank = TribeGroupRank.objects.create(
            tribe_group=self.tribe_group,
            code="strategic",
            name="Strategic FC",
            group=self.strategic_group,
        )
        TribeGroupRank.objects.create(
            tribe_group=self.tribe_group,
            code="skirmish",
            name="Skirmish FC",
            group=self.skirmish_group,
        )
        self.user = User.objects.create_user(username="fc")
        self.membership = TribeGroupMembership.objects.create(
            user=self.user,
            tribe_group=self.tribe_group,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )

    def test_setting_rank_adds_linked_auth_group(self):
        self.membership.rank = self.strategic_rank
        self.membership.save()

        self.assertIn(self.strategic_group, self.user.groups.all())

    def test_changing_rank_swaps_auth_groups(self):
        self.membership.rank = self.strategic_rank
        self.membership.save()
        self.membership.rank = TribeGroupRank.objects.get(
            tribe_group=self.tribe_group, code="skirmish"
        )
        self.membership.save()

        self.assertNotIn(self.strategic_group, self.user.groups.all())
        self.assertIn(self.skirmish_group, self.user.groups.all())

    def test_clearing_rank_removes_rank_auth_groups(self):
        self.membership.rank = self.strategic_rank
        self.membership.save()
        self.membership.rank = None
        self.membership.save()

        self.assertNotIn(self.strategic_group, self.user.groups.all())

    def test_inactive_membership_removes_rank_auth_groups(self):
        self.membership.rank = self.strategic_rank
        self.membership.save()
        self.membership.status = TribeGroupMembership.STATUS_INACTIVE
        self.membership.left_at = timezone.now()
        self.membership.history_inactive_reason = "removed"
        self.membership.save()

        self.assertNotIn(self.strategic_group, self.user.groups.all())


class TribeMembershipDiscordFailClosedTestCase(TestCase):
    """Inactive membership must not stick when Discord role remove fails."""

    def setUp(self):
        # Reconnect Discord m2m sync only (module setup disconnects it).
        # Leave group_post_save disconnected so Group.create does not hit Discord.
        django_signals.m2m_changed.connect(
            user_group_changed,
            sender=User.groups.through,
            dispatch_uid="user_group_changed",
        )
        self.tribe_auth_group = Group.objects.create(name="Tribe FC Auth")
        self.group_auth_group = Group.objects.create(name="Group FC Auth")
        self.tribe = Tribe.objects.create(
            name="Capitals FC",
            slug="capitals-fc",
            group=self.tribe_auth_group,
        )
        self.tribe_group = TribeGroup.objects.create(
            tribe=self.tribe,
            name="Dreads FC",
            group=self.group_auth_group,
        )
        self.user = User.objects.create(username="tribe_fc_user")

    def tearDown(self):
        django_signals.m2m_changed.disconnect(
            user_group_changed,
            sender=User.groups.through,
            dispatch_uid="user_group_changed",
        )

    @patch("discord.signals.discord")
    def test_inactive_rolls_back_when_discord_remove_fails(self, discord_mock):
        discord_mock.get_roles.return_value = []
        discord_mock.create_role.return_value.json.return_value = {"id": 200}
        DiscordUser.objects.create(id=200, discord_tag="t", user=self.user)
        for group, role_id in (
            (self.group_auth_group, 201),
            (self.tribe_auth_group, 202),
        ):
            if not DiscordRole.objects.filter(group=group).exists():
                DiscordRole.objects.create(
                    role_id=role_id, name=group.name, group=group
                )

        self.user.groups.add(self.group_auth_group)
        self.user.groups.add(self.tribe_auth_group)

        membership = TribeGroupMembership.objects.create(
            user=self.user,
            tribe_group=self.tribe_group,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )

        discord_mock.remove_user_role.side_effect = ConnectionError("down")
        membership.status = TribeGroupMembership.STATUS_INACTIVE
        membership.left_at = timezone.now()
        membership.history_inactive_reason = "left"

        with self.assertRaises(DiscordRoleAssignmentError):
            with transaction.atomic():
                membership.save()

        membership.refresh_from_db()
        self.assertEqual(membership.status, TribeGroupMembership.STATUS_ACTIVE)
        self.assertIn(self.group_auth_group, self.user.groups.all())
