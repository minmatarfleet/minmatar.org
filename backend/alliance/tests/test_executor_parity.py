"""alliance.health.executor keeps the People Team audience it replaced.

``is_alliance_executor`` used to be ``is_superuser or in "People Team"``.
It now goes through ``can_use_feature``. For every combination of
superuser flag, account state, community status and auth groups, the new
check must agree with the old one, except for the two intended changes:
a deactivated account loses access, and so does a People Team member who
is on leave (unless a superuser).
"""

from itertools import product

from django.contrib.auth.models import Group, User
from django.db.models import signals

from alliance.helpers.access import can_mutate_status, is_alliance_executor
from app.test import TestCase
from groups.helpers.feature_access import clear_feature_cache
from groups.management.commands.sync_pilot_features import (
    Command as SyncFeatures,
)
from groups.models import PilotFeature, UserCommunityStatus

PEOPLE = "People Team"
TECH = "Technology Team"
OTHER = "Some Other Group"

STATUSES = (None, "active", "trial", "on_leave")
GROUP_SETS = ((), (PEOPLE,), (TECH,), (PEOPLE, TECH), (OTHER,))


def legacy_is_alliance_executor(user) -> bool:
    """The check this replaced, verbatim."""
    if not user or not user.is_authenticated:
        return False
    return bool(user.is_superuser) or user.groups.filter(name=PEOPLE).exists()


def intended_change(user, status) -> bool:
    """Where the new check may say no while the old one said yes."""
    if not user.is_active:
        return True
    return status == "on_leave" and not user.is_superuser


class AllianceExecutorParityTestCase(TestCase):
    def setUp(self):
        super().setUp()
        signals.post_save.disconnect(
            sender=Group, dispatch_uid="group_post_save"
        )
        signals.m2m_changed.disconnect(
            sender=User.groups.through, dispatch_uid="user_group_changed"
        )
        self.groups = {
            name: Group.objects.get_or_create(name=name)[0]
            for name in (PEOPLE, TECH, OTHER)
        }
        clear_feature_cache()
        SyncFeatures().handle()
        clear_feature_cache()

        self.cases = []
        for index, (superuser, active, status, group_names) in enumerate(
            product((False, True), (True, False), STATUSES, GROUP_SETS)
        ):
            user = User.objects.create(
                username=f"case{index}",
                is_superuser=superuser,
                is_active=active,
            )
            for name in group_names:
                user.groups.add(self.groups[name])
            if status:
                UserCommunityStatus.objects.create(user=user, status=status)
            self.cases.append((user, status, group_names))

    def test_matrix_matches_except_on_leave_and_deactivated(self):
        changed = []
        for user, status, group_names in self.cases:
            old = legacy_is_alliance_executor(user)
            new = is_alliance_executor(user)
            label = (user.is_superuser, user.is_active, status, group_names)
            if old == new:
                continue
            # The only allowed difference is a loss of access, and only for
            # the two intended reasons.
            self.assertTrue(old, label)
            self.assertFalse(new, label)
            self.assertTrue(intended_change(user, status), label)
            changed.append(label)

        # Active, not-on-leave People Team members and superusers all keep
        # access; the matrix really exercises the intended changes.
        self.assertIn((False, True, "on_leave", (PEOPLE,)), changed)
        self.assertIn((False, False, "active", (PEOPLE,)), changed)
        self.assertNotIn((True, True, "on_leave", ()), changed)
        for user, status, group_names in self.cases:
            if (
                user.is_active
                and status != "on_leave"
                and (PEOPLE in group_names or user.is_superuser)
            ):
                self.assertTrue(is_alliance_executor(user), user.username)

    def test_status_mutation_follows_the_same_rule(self):
        target = User.objects.create(username="target")
        for user, status, _ in self.cases:
            self.assertEqual(
                can_mutate_status(user, target),
                is_alliance_executor(user),
                (user.username, status),
            )

    def test_removing_the_wiring_closes_it_to_the_group(self):
        PilotFeature.objects.get(
            code="alliance.health.executor"
        ).auth_groups.clear()
        clear_feature_cache()
        member = User.objects.create(username="people-member")
        member.groups.add(self.groups[PEOPLE])
        self.assertFalse(is_alliance_executor(member))
