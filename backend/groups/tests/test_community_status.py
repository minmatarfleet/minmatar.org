"""Tests for UserCommunityStatus, sync_user_community_groups, and history."""

from django.contrib.auth.models import Group, User
from django.db.models import signals

from app.test import TestCase
from eveonline.models import EveAlliance, EveCharacter, EveCorporation
from eveonline.helpers.characters import set_primary_character
from esi.models import Token

from groups.helpers import sync_user_community_groups
from groups.models import (
    AffiliationType,
    UserAffiliation,
    UserCommunityStatus,
    UserCommunityStatusHistory,
)


class SyncUserCommunityGroupsTestCase(TestCase):
    """Tests for sync_user_community_groups."""

    def setUp(self):
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
        signals.m2m_changed.disconnect(
            sender=User.groups.through,
            dispatch_uid="user_group_changed",
        )
        super().setUp()

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

    def test_requires_trial_creates_trial_status(self):
        self.assertFalse(
            UserCommunityStatus.objects.filter(user=self.user).exists()
        )
        UserAffiliation.objects.create(
            user=self.user, affiliation=self.affiliation_type
        )
        ucs = UserCommunityStatus.objects.get(user=self.user)
        self.assertEqual(ucs.status, UserCommunityStatus.STATUS_TRIAL)
