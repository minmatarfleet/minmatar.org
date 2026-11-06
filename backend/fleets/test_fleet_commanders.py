"""GET /fleets/commanders: the Fleet Commanders tribe group for the Commanders tab."""

from datetime import timedelta

from django.utils import timezone

from fleets.test_group_fleets import GroupFleetTestBase
from tribes.models import TribeGroup, TribeGroupMembership, TribeGroupRank


class FleetCommandersTests(GroupFleetTestBase):
    def setUp(self):
        super().setUp()
        self.fc_group = TribeGroup.objects.create(
            tribe=self.group.tribe,
            name="Fleet Commanders",
            code="pulse.fleet-commanders",
        )
        self.rank = TribeGroupRank.objects.create(
            tribe_group=self.fc_group,
            name="Strategic FC",
            code="strategic",
            sort_order=1,
        )

    def join(self, user, rank=None, status=TribeGroupMembership.STATUS_ACTIVE):
        return TribeGroupMembership.objects.create(
            user=user, tribe_group=self.fc_group, rank=rank, status=status
        )

    def test_lists_active_members_with_level_and_activity(self):
        self.join(self.fc, rank=self.rank)
        self.join(self.member)
        self.join(self.outsider, status=TribeGroupMembership.STATUS_PENDING)
        self.alliance_fleet(
            created_by=self.fc, start_time=timezone.now() - timedelta(days=1)
        )

        rows = self.call("get", "/commanders", self.member).json()
        by_user = {row["user_id"]: row for row in rows}

        self.assertEqual(set(by_user), {self.fc.id, self.member.id})
        self.assertEqual(by_user[self.fc.id]["rank_name"], "Strategic FC")
        self.assertIsNotNone(by_user[self.fc.id]["last_led"])
        self.assertIsNone(by_user[self.member.id]["rank_name"])
        self.assertIsNone(by_user[self.member.id]["last_led"])

    def test_most_recent_leader_first_and_never_led_last(self):
        self.join(self.member)
        self.join(self.fc)
        self.alliance_fleet(
            created_by=self.fc, start_time=timezone.now() - timedelta(days=3)
        )

        rows = self.call("get", "/commanders", self.member).json()

        self.assertEqual(
            [row["user_id"] for row in rows], [self.fc.id, self.member.id]
        )
