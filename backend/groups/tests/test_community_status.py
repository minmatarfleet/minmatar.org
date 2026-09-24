"""Tests for UserCommunityStatus, sync_user_community_groups, and history."""

from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.db.models import signals

from app.test import TestCase
from discord.signals import group_post_save, user_group_changed
from eveonline.models import EveAlliance, EveCharacter, EveCorporation
from eveonline.helpers.characters import set_primary_character
from esi.models import Token

from groups.helpers import (
    reconcile_community_status_for_affiliation,
    sync_user_community_groups,
)
from groups.helpers.feature_access import can_use_feature
from groups.models import (
    AffiliationType,
    UserAffiliation,
    UserCommunityStatus,
    UserCommunityStatusHistory,
)
from tribes.models import Tribe, TribeGroup, TribeGroupMembership


def _reconnect_discord_group_signals():
    signals.post_save.connect(
        group_post_save,
        sender=Group,
        dispatch_uid="group_post_save",
    )
    signals.m2m_changed.connect(
        user_group_changed,
        sender=User.groups.through,
        dispatch_uid="user_group_changed",
    )


class SyncUserCommunityGroupsTestCase(TestCase):
    """Tests for sync_user_community_groups."""

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
        self.trial_group, _ = Group.objects.get_or_create(name="Trial")
        self.on_leave_group, _ = Group.objects.get_or_create(name="On Leave")
        self.affiliation_type = AffiliationType.objects.create(
            name="Alliance",
            description="",
            image_url="",
            group=self.affiliation_group,
            priority=1,
        )

    def tearDown(self):
        _reconnect_discord_group_signals()
        super().tearDown()

    def test_active_adds_affiliation_group_only(self):
        UserAffiliation.objects.create(
            user=self.user, affiliation=self.affiliation_type
        )
        UserCommunityStatus.objects.create(
            user=self.user, status=UserCommunityStatus.STATUS_ACTIVE
        )
        sync_user_community_groups(self.user)
        group_names = set(self.user.groups.values_list("name", flat=True))
        self.assertIn("Alliance", group_names)
        self.assertNotIn("Trial", group_names)
        self.assertNotIn("On Leave", group_names)

    def test_trial_adds_affiliation_and_trial_groups(self):
        UserAffiliation.objects.create(
            user=self.user, affiliation=self.affiliation_type
        )
        UserCommunityStatus.objects.create(
            user=self.user, status=UserCommunityStatus.STATUS_TRIAL
        )
        sync_user_community_groups(self.user)
        group_names = set(self.user.groups.values_list("name", flat=True))
        self.assertIn("Alliance", group_names)
        self.assertIn("Trial", group_names)
        self.assertNotIn("On Leave", group_names)

    def test_on_leave_adds_on_leave_group_only(self):
        UserAffiliation.objects.create(
            user=self.user, affiliation=self.affiliation_type
        )
        UserCommunityStatus.objects.create(
            user=self.user, status=UserCommunityStatus.STATUS_ON_LEAVE
        )
        sync_user_community_groups(self.user)
        group_names = set(self.user.groups.values_list("name", flat=True))
        self.assertNotIn("Alliance", group_names)
        self.assertNotIn("Trial", group_names)
        self.assertIn("On Leave", group_names)

    def test_guest_on_leave_heals_to_active_guest(self):
        """Former alliance members stuck on leave become Guest, not On Leave."""
        guest_group, _ = Group.objects.get_or_create(name="Guest")
        guest_type = AffiliationType.objects.create(
            name="Guest",
            description="",
            image_url="",
            group=guest_group,
            priority=0,
            requires_trial=False,
            default=True,
        )
        UserAffiliation.objects.create(user=self.user, affiliation=guest_type)
        UserCommunityStatus.objects.create(
            user=self.user, status=UserCommunityStatus.STATUS_ON_LEAVE
        )
        self.user.groups.add(self.on_leave_group)
        self.user.groups.add(self.affiliation_group)

        reconcile_community_status_for_affiliation(self.user)
        sync_user_community_groups(self.user)

        ucs = UserCommunityStatus.objects.get(user=self.user)
        self.assertEqual(ucs.status, UserCommunityStatus.STATUS_ACTIVE)
        group_names = set(self.user.groups.values_list("name", flat=True))
        self.assertIn("Guest", group_names)
        self.assertNotIn("On Leave", group_names)
        self.assertNotIn("Alliance", group_names)
        history = (
            UserCommunityStatusHistory.objects.filter(
                user=self.user,
                from_status=UserCommunityStatus.STATUS_ON_LEAVE,
                to_status=UserCommunityStatus.STATUS_ACTIVE,
            )
            .order_by("-id")
            .first()
        )
        self.assertIsNotNone(history)
        self.assertEqual(history.reason, "No longer Alliance")

    def test_cool_off_strips_groups_roles_and_tribes(self):
        extra_group = Group.objects.create(name="Mining Tribe")
        self.user.groups.add(self.affiliation_group, extra_group)
        UserAffiliation.objects.create(
            user=self.user, affiliation=self.affiliation_type
        )
        tribe = Tribe.objects.create(name="Supply", slug="supply-cool-off")
        tribe_group = TribeGroup.objects.create(
            tribe=tribe,
            name="Mining",
            code="supply.mining-cool-off",
            group=extra_group,
        )
        TribeGroupMembership.objects.create(
            user=self.user,
            tribe_group=tribe_group,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        with patch(
            "discord.signals.ensure_cool_off_discord_role"
        ) as ensure_role:
            UserCommunityStatus.objects.create(
                user=self.user, status=UserCommunityStatus.STATUS_COOL_OFF
            )

        ensure_role.assert_called_once()
        group_names = set(self.user.groups.values_list("name", flat=True))
        self.assertEqual(group_names, {"Cool Off"})
        membership = TribeGroupMembership.objects.get(user=self.user)
        self.assertEqual(
            membership.status, TribeGroupMembership.STATUS_INACTIVE
        )
        self.user.is_superuser = True
        self.user.save(update_fields=["is_superuser"])
        self.assertFalse(can_use_feature(self.user, "fleets.view"))

    def test_cool_off_is_not_cleared_by_affiliation_reconcile(self):
        guest_group, _ = Group.objects.get_or_create(name="Guest")
        guest_type = AffiliationType.objects.create(
            name="Guest",
            description="",
            image_url="",
            group=guest_group,
            priority=2,
            requires_trial=False,
            default=True,
        )
        UserAffiliation.objects.create(user=self.user, affiliation=guest_type)
        with patch("discord.signals.ensure_cool_off_discord_role"):
            UserCommunityStatus.objects.create(
                user=self.user, status=UserCommunityStatus.STATUS_COOL_OFF
            )

        reconcile_community_status_for_affiliation(self.user)

        ucs = UserCommunityStatus.objects.get(user=self.user)
        self.assertEqual(ucs.status, UserCommunityStatus.STATUS_COOL_OFF)
        group_names = set(self.user.groups.values_list("name", flat=True))
        self.assertEqual(group_names, {"Cool Off"})
        self.assertNotIn("Guest", group_names)

    def test_no_status_treated_as_active(self):
        UserAffiliation.objects.create(
            user=self.user, affiliation=self.affiliation_type
        )
        sync_user_community_groups(self.user)
        group_names = set(self.user.groups.values_list("name", flat=True))
        self.assertIn("Alliance", group_names)
        self.assertNotIn("Trial", group_names)


class UserCommunityStatusHistoryTestCase(TestCase):
    """Tests that status changes create history rows."""

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

    def tearDown(self):
        _reconnect_discord_group_signals()
        super().tearDown()

    def test_history_created_on_status_change(self):
        ucs = UserCommunityStatus.objects.create(
            user=self.user, status=UserCommunityStatus.STATUS_TRIAL
        )
        self.assertEqual(
            UserCommunityStatusHistory.objects.filter(user=self.user).count(),
            1,
        )
        first = UserCommunityStatusHistory.objects.get(user=self.user)
        self.assertIsNone(first.from_status)
        self.assertEqual(first.to_status, UserCommunityStatus.STATUS_TRIAL)

        ucs.status = UserCommunityStatus.STATUS_ACTIVE
        ucs.save()
        self.assertEqual(
            UserCommunityStatusHistory.objects.filter(user=self.user).count(),
            2,
        )
        second = (
            UserCommunityStatusHistory.objects.filter(user=self.user)
            .order_by("-changed_at")
            .first()
        )
        self.assertEqual(second.from_status, UserCommunityStatus.STATUS_TRIAL)
        self.assertEqual(second.to_status, UserCommunityStatus.STATUS_ACTIVE)


class RequiresTrialTestCase(TestCase):
    """Tests that new UserAffiliation with requires_trial creates trial status."""

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
        self.trial_group, _ = Group.objects.get_or_create(name="Trial")
        self.corp = EveCorporation.objects.create(corporation_id=98726134)
        self.alliance = EveAlliance.objects.create(alliance_id=99011978)
        self.affiliation_type = AffiliationType.objects.create(
            name="Alliance",
            description="",
            image_url="",
            group=self.affiliation_group,
            priority=1,
            requires_trial=True,
        )
        self.affiliation_type.corporations.add(self.corp)
        self.affiliation_type.alliances.add(self.alliance)
        token = Token.objects.create(character_id=123, user=self.user)
        self.char = EveCharacter.objects.create(
            character_id=123,
            character_name="Test",
            corporation_id=self.corp.corporation_id,
            alliance_id=self.alliance.alliance_id,
        )
        self.char.token = token
        self.char.save()
        set_primary_character(self.user, self.char)

    def tearDown(self):
        _reconnect_discord_group_signals()
        super().tearDown()

    def test_requires_trial_creates_trial_status(self):
        self.assertFalse(
            UserCommunityStatus.objects.filter(user=self.user).exists()
        )
        UserAffiliation.objects.create(
            user=self.user, affiliation=self.affiliation_type
        )
        ucs = UserCommunityStatus.objects.get(user=self.user)
        self.assertEqual(ucs.status, UserCommunityStatus.STATUS_TRIAL)

    def test_affiliation_without_requires_trial_clears_trial_status(self):
        """When user's affiliation changes from requires_trial to non-requires_trial, status becomes active."""
        UserAffiliation.objects.create(
            user=self.user, affiliation=self.affiliation_type
        )
        ucs = UserCommunityStatus.objects.get(user=self.user)
        self.assertEqual(ucs.status, UserCommunityStatus.STATUS_TRIAL)

        guest_group, _ = Group.objects.get_or_create(name="Guest")
        guest_affiliation = AffiliationType.objects.create(
            name="Guest",
            description="",
            image_url="",
            group=guest_group,
            priority=0,
            requires_trial=False,
        )
        UserAffiliation.objects.filter(user=self.user).delete()
        UserAffiliation.objects.create(
            user=self.user, affiliation=guest_affiliation
        )
        ucs.refresh_from_db()
        self.assertEqual(ucs.status, UserCommunityStatus.STATUS_ACTIVE)

    def test_affiliation_without_requires_trial_clears_on_leave_status(self):
        """Alliance → Guest clears imposed leave so Discord drops On Leave."""
        UserAffiliation.objects.create(
            user=self.user, affiliation=self.affiliation_type
        )
        ucs = UserCommunityStatus.objects.get(user=self.user)
        ucs.status = UserCommunityStatus.STATUS_ON_LEAVE
        ucs.save()
        self.assertEqual(ucs.status, UserCommunityStatus.STATUS_ON_LEAVE)

        guest_group, _ = Group.objects.get_or_create(name="Guest")
        guest_affiliation = AffiliationType.objects.create(
            name="Guest",
            description="",
            image_url="",
            group=guest_group,
            priority=0,
            requires_trial=False,
        )
        UserAffiliation.objects.filter(user=self.user).delete()
        UserAffiliation.objects.create(
            user=self.user, affiliation=guest_affiliation
        )
        ucs.refresh_from_db()
        self.assertEqual(ucs.status, UserCommunityStatus.STATUS_ACTIVE)
        group_names = set(self.user.groups.values_list("name", flat=True))
        self.assertIn("Guest", group_names)
        self.assertNotIn("On Leave", group_names)
