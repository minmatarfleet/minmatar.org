"""Track mining on fleets, and the group setting that turns it on by default."""

from unittest.mock import patch

from django.utils import timezone

from fleets.models import EveFleet
from fleets.test_group_fleets import (  # pylint: disable=unused-import
    GroupFleetTestBase,
    setUpModule,
    tearDownModule,
)
from tribes.models import TribeGroup


@patch("fleets.endpoints.helpers.queue_channel_message")
class TrackMiningCreateTests(GroupFleetTestBase):
    def setUp(self):
        super().setUp()
        self.group.fleet_policy = TribeGroup.POLICY_MEMBERS
        self.group.save()

    def create(self, user, **fields):
        response = self.call("post", "", user, self.create_payload(**fields))
        self.assertEqual(response.status_code, 200, response.content)
        return response, EveFleet.objects.get(id=response.json()["id"])

    def test_group_fleet_takes_the_group_default_when_left_out(self, _):
        self.group.track_mining_by_default = True
        self.group.save()

        response, fleet = self.create(self.fc)

        self.assertTrue(fleet.track_mining)
        self.assertTrue(response.json()["track_mining"])

    def test_fc_can_turn_the_default_off(self, _):
        self.group.track_mining_by_default = True
        self.group.save()

        _, fleet = self.create(self.fc, track_mining=False)

        self.assertFalse(fleet.track_mining)

    def test_group_without_the_default_starts_off(self, _):
        _, fleet = self.create(self.fc)

        self.assertFalse(fleet.track_mining)

    def test_fc_can_turn_it_on_without_the_default(self, _):
        _, fleet = self.create(self.fc, track_mining=True)

        self.assertTrue(fleet.track_mining)

    def test_alliance_fleet_starts_off_and_can_be_turned_on(self, _):
        _, off = self.create(self.outsider, host_group_id=None)
        _, on = self.create(
            self.outsider, host_group_id=None, track_mining=True
        )

        self.assertIsNone(off.host_group)
        self.assertFalse(off.track_mining)
        self.assertTrue(on.track_mining)


@patch("fleets.endpoints.helpers.queue_channel_message")
class TrackMiningUpdateTests(GroupFleetTestBase):
    def test_patch_turns_it_on_and_leaving_it_out_keeps_it(self, _):
        fleet = self.group_fleet()

        response = self.call(
            "patch", f"/{fleet.id}", self.fc, {"track_mining": True}
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["track_mining"])

        response = self.call(
            "patch", f"/{fleet.id}", self.fc, {"description": "Moon op"}
        )
        self.assertEqual(response.status_code, 200, response.content)
        fleet.refresh_from_db()
        self.assertTrue(fleet.track_mining)

    def test_changing_the_group_default_leaves_existing_fleets(self, _):
        fleet = self.group_fleet()

        self.group.track_mining_by_default = True
        self.group.save()

        fleet.refresh_from_db()
        self.assertFalse(fleet.track_mining)

    def test_detail_reports_it(self, _):
        fleet = self.group_fleet(track_mining=True)

        response = self.call("get", f"/{fleet.id}", self.fc)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["track_mining"])


@patch("fleets.endpoints.helpers.queue_channel_message")
class TrackMiningCopyTests(GroupFleetTestBase):
    def setUp(self):
        super().setUp()
        self.group.fleet_policy = TribeGroup.POLICY_MEMBERS
        self.group.save()

    def copy(self, fleet):
        start = (fleet.start_time + timezone.timedelta(days=7)).isoformat()
        response = self.call(
            "post", f"/{fleet.id}/copy", self.fc, {"start_time": start}
        )
        self.assertEqual(response.status_code, 200, response.content)
        return EveFleet.objects.get(id=response.json()["id"])

    def test_copy_keeps_the_fleets_choice_not_the_group_default(self, _):
        self.group.track_mining_by_default = True
        self.group.save()

        self.assertFalse(self.copy(self.group_fleet()).track_mining)
        self.assertTrue(
            self.copy(self.group_fleet(track_mining=True)).track_mining
        )
