"""Who may publish as a tribe group, and who sees members-only items."""

from django.contrib.auth.models import AnonymousUser

from app.test import TestCase
from tribes.helpers.publishing import (
    KINDS,
    can_publish,
    publishable_groups,
    visible_group_ids,
)
from tribes.models import TribeGroup, TribeGroupMembership
from tribes.tests.publishing_fixtures import (
    add_member,
    make_tribe_group,
    make_user,
)


class CanPublishTests(TestCase):
    def setUp(self):
        super().setUp()
        self.group = make_tribe_group()
        self.other = make_tribe_group(
            "Carriers", "capitals.carriers", role_id=None
        )
        self.member = make_user("member")
        add_member(self.group, self.member)
        self.chosen = make_user("chosen")
        add_member(self.group, self.chosen)
        self.pending = make_user("pending")
        add_member(
            self.group, self.pending, TribeGroupMembership.STATUS_PENDING
        )
        self.outsider = make_user("outsider")
        self.chief = make_user("chief")
        self.group.chief = self.chief
        self.group.save()
        self.tribe_chief = make_user("tribe_chief")
        self.group.tribe.chief = self.tribe_chief
        self.group.tribe.save()
        self.group.post_publishers.add(self.chosen)
        self.group.fleet_publishers.add(self.chosen)
        self.group.event_publishers.add(self.chosen)
        # Chosen but no longer a member: the list alone isn't enough.
        self.left = make_user("left")
        self.group.post_publishers.add(self.left)

    def matrix(self, policy):
        for kind in KINDS:
            setattr(self.group, f"{kind}_policy", policy)
        self.group.save()
        return {
            name: {
                kind: can_publish(getattr(self, name), self.group, kind)
                for kind in KINDS
            }
            for name in (
                "member",
                "chosen",
                "pending",
                "outsider",
                "chief",
                "tribe_chief",
                "left",
            )
        }

    def assert_publishers(self, policy, expected):
        result = self.matrix(policy)
        for name, kinds in result.items():
            for kind, allowed in kinds.items():
                with self.subTest(policy=policy, user=name, kind=kind):
                    self.assertEqual(allowed, name in expected)

    def test_chiefs_policy(self):
        self.assert_publishers(
            TribeGroup.POLICY_CHIEFS, {"chief", "tribe_chief"}
        )

    def test_chosen_policy(self):
        self.assert_publishers(
            TribeGroup.POLICY_CHOSEN, {"chief", "tribe_chief", "chosen"}
        )

    def test_members_policy(self):
        self.assert_publishers(
            TribeGroup.POLICY_MEMBERS,
            {"chief", "tribe_chief", "chosen", "member"},
        )

    def test_superuser_and_anonymous(self):
        admin = make_user("admin")
        admin.is_superuser = True
        admin.save()
        self.assertTrue(can_publish(admin, self.group, "event"))
        self.assertFalse(can_publish(AnonymousUser(), self.group, "post"))

    def test_inactive_group_publishes_nothing(self):
        self.group.is_active = False
        self.group.save()
        self.assertFalse(can_publish(self.chief, self.group, "post"))

    def test_kinds_are_independent(self):
        self.group.post_policy = TribeGroup.POLICY_MEMBERS
        self.group.save()
        self.assertTrue(can_publish(self.member, self.group, "post"))
        self.assertFalse(can_publish(self.member, self.group, "fleet"))
        self.assertFalse(can_publish(self.member, self.group, "event"))

    def test_publishable_groups(self):
        self.group.fleet_policy = TribeGroup.POLICY_MEMBERS
        self.group.save()
        self.assertEqual(
            publishable_groups(self.member, "fleet"), [self.group]
        )
        self.assertEqual(publishable_groups(self.member, "post"), [])
        self.assertEqual(publishable_groups(self.chief, "post"), [self.group])

    def test_visible_group_ids(self):
        self.assertEqual(visible_group_ids(self.member), {self.group.pk})
        self.assertEqual(visible_group_ids(self.pending), frozenset())
        self.assertEqual(visible_group_ids(self.chief), {self.group.pk})
        # The tribe chief manages every group in the tribe.
        self.assertEqual(
            visible_group_ids(self.tribe_chief),
            {self.group.pk, self.other.pk},
        )
        self.assertEqual(visible_group_ids(AnonymousUser()), frozenset())
