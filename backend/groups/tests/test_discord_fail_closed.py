"""Tests for community group reconciler and fail-closed source behavior."""

from unittest.mock import MagicMock, patch

from django.contrib.auth.models import Group, User
from django.db import transaction
from django.db.models import signals

from app.test import TestCase
from discord.exceptions import DiscordRoleAssignmentError
from discord.models import DiscordUser
from discord.testing import reconnect_discord_group_signals
from groups.helpers import sync_user_community_groups
from groups.models import (
    AffiliationType,
    UserAffiliation,
    UserCommunityStatus,
)


class SyncCommunityGroupsReconcilerTestCase(TestCase):
    """Desired-state community group sync retries Discord strip/add."""

    def setUp(self):
        signals.post_save.disconnect(
            sender=Group,
            dispatch_uid="group_post_save",
        )
        signals.m2m_changed.disconnect(
            sender=User.groups.through,
            dispatch_uid="user_group_changed",
        )
        super().setUp()
        self.affiliation_group, _ = Group.objects.get_or_create(
            name="Alliance"
        )
        self.guest_group, _ = Group.objects.get_or_create(name="Guest")
        Group.objects.get_or_create(name="Trial")
        Group.objects.get_or_create(name="On Leave")
        self.alliance_type = AffiliationType.objects.create(
            name="Alliance",
            description="",
            image_url="",
            group=self.affiliation_group,
            priority=2,
        )
        self.guest_type = AffiliationType.objects.create(
            name="Guest",
            description="",
            image_url="",
            group=self.guest_group,
            priority=1,
            default=True,
        )

    def test_reconciler_strips_stale_alliance_when_guest(self):
        UserAffiliation.objects.create(
            user=self.user, affiliation=self.guest_type
        )
        UserCommunityStatus.objects.create(
            user=self.user, status=UserCommunityStatus.STATUS_ACTIVE
        )
        # Stale Alliance group left from a prior failed Discord remove
        self.user.groups.add(self.affiliation_group)

        sync_user_community_groups(self.user)

        names = set(self.user.groups.values_list("name", flat=True))
        self.assertNotIn("Alliance", names)
        self.assertIn("Guest", names)

    def test_sync_user_community_groups_per_group(self):
        UserAffiliation.objects.create(
            user=self.user, affiliation=self.alliance_type
        )
        UserCommunityStatus.objects.create(
            user=self.user, status=UserCommunityStatus.STATUS_ACTIVE
        )
        sync_user_community_groups(self.user)
        self.assertIn(self.affiliation_group, self.user.groups.all())


class AffiliationAtomicRollbackTestCase(TestCase):
    """Affiliation save rolls back when Discord group sync fails."""

    def setUp(self):
        reconnect_discord_group_signals()
        super().setUp()

    @patch("discord.signals.discord")
    def test_affiliation_create_rolls_back_on_discord_add_failure(
        self, discord_mock
    ):
        discord_mock.get_roles.return_value = []
        role_ids = iter(range(100, 200))

        def _create_role(role_name):
            mock = MagicMock()
            mock.json.return_value = {"id": next(role_ids)}
            assert role_name
            return mock

        discord_mock.create_role.side_effect = _create_role
        DiscordUser.objects.create(id=100, discord_tag="t", user=self.user)
        alliance_group = Group.objects.create(name="Alliance FC")
        affiliation_type = AffiliationType.objects.create(
            name="Alliance FC",
            description="",
            image_url="",
            group=alliance_group,
            priority=10,
        )
        discord_mock.add_user_role.side_effect = ConnectionError("down")

        with self.assertRaises(DiscordRoleAssignmentError):
            with transaction.atomic():
                UserAffiliation.objects.create(
                    user=self.user, affiliation=affiliation_type
                )

        self.assertFalse(
            UserAffiliation.objects.filter(user=self.user).exists()
        )
        self.assertFalse(
            self.user.groups.filter(pk=alliance_group.pk).exists()
        )
