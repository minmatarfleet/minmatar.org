"""Each fleet decides who sees it: the fleet list filters by audience the
same way the fleet detail does, and group publishers can load the fleet
form (docs/tribes/group-fleet-scheduling-analysis.md)."""

from datetime import timedelta

from django.contrib.auth.models import Group, Permission, User
from django.db.models import signals
from django.test import Client
from django.utils import timezone

from app.test import TestCase
from app.testing import make_token
from eveonline.models import EveLocation
from fleets.models import EveFleet, EveFleetAudience
from fleets.tests import setup_fleet_reference_data
from groups.helpers.feature_access import clear_feature_cache
from groups.management.commands.sync_pilot_features import (
    Command as SyncCommand,
)
from groups.models import (
    AffiliationType,
    PilotFeature,
    UserAffiliation,
    UserCommunityStatus,
)
from tribes.models import TribeGroup
from tribes.tests.publishing_fixtures import (
    add_member,
    make_tribe_group,
    make_user,
)

BASE_URL = "/api/fleets"


def setUpModule():
    signals.post_save.disconnect(
        sender=EveFleet, dispatch_uid="update_fleet_schedule_on_save"
    )
    signals.post_save.disconnect(sender=Group, dispatch_uid="group_post_save")
    signals.m2m_changed.disconnect(
        sender=User.groups.through, dispatch_uid="user_group_changed"
    )


def tearDownModule():
    # pylint: disable=import-outside-toplevel
    from discord.testing import reconnect_discord_group_signals
    from fleets.signals import update_fleet_schedule_on_save

    signals.post_save.connect(
        update_fleet_schedule_on_save,
        sender=EveFleet,
        dispatch_uid="update_fleet_schedule_on_save",
    )
    reconnect_discord_group_signals()


class FleetAudienceTestBase(TestCase):
    """Alliance and Associate pilots decided by affiliation, as in
    production: no legacy fleet permissions unless a test adds them."""

    def setUp(self):
        super().setUp()
        clear_feature_cache()
        SyncCommand().handle()
        setup_fleet_reference_data()
        self.alliance = self._affiliation("Alliance", 30)
        self.associate = self._affiliation("Associate", 20)
        view = PilotFeature.objects.get(code="fleets.view")
        view.affiliations.set([self.alliance, self.associate])
        create = PilotFeature.objects.get(code="fleets.create")
        create.affiliations.set([self.alliance])
        clear_feature_cache()

        self.open_audience = EveFleetAudience.objects.get(name="Test Audience")
        self.alliance_audience = EveFleetAudience.objects.create(
            name="Alliance only"
        )
        self.alliance_audience.groups.add(self.alliance.group)
        self.associate_audience = EveFleetAudience.objects.create(
            name="Associates only"
        )
        self.associate_audience.groups.add(self.associate.group)

        self.group = make_tribe_group(allow_open_fleets=True)
        self.alliance_pilot = self._pilot("alliance_pilot", self.alliance)
        self.member = self._pilot("associate_member", self.associate)
        add_member(self.group, self.member)
        self.outsider = self._pilot("associate_outsider", self.associate)
        self.fc = self._pilot("group_fc", self.alliance)
        add_member(self.group, self.fc)

    def tearDown(self):
        clear_feature_cache()
        super().tearDown()

    def _affiliation(self, name, priority):
        return AffiliationType.objects.create(
            name=name,
            group=Group.objects.create(name=f"{name} affiliation"),
            priority=priority,
        )

    def _pilot(self, username, affiliation):
        user = make_user(username)
        UserAffiliation.objects.create(user=user, affiliation=affiliation)
        user.groups.add(affiliation.group)
        return user

    def call(self, path, user):
        return Client().get(
            f"{BASE_URL}{path}",
            HTTP_AUTHORIZATION=f"Bearer {make_token(user)}",
        )

    def fleet(self, **fields) -> EveFleet:
        values = {
            "type": "training",
            "description": "Op",
            "start_time": timezone.now() + timedelta(hours=2),
            "created_by": self.fc,
            "location": EveLocation.objects.first(),
            "status": "pending",
        }
        values.update(fields)
        return EveFleet.objects.create(**values)

    def listed_ids(self, user) -> set[int]:
        response = self.call("/v3?fleet_filter=upcoming", user)
        self.assertEqual(response.status_code, 200, response.content)
        return {fleet["id"] for fleet in response.json()}


class FleetListAudienceTests(FleetAudienceTestBase):
    def setUp(self):
        super().setUp()
        self.open_fleet = self.fleet(audience=self.open_audience)
        self.alliance_fleet = self.fleet(audience=self.alliance_audience)
        self.associate_fleet = self.fleet(audience=self.associate_audience)
        self.members_only = self.fleet(
            host_group=self.group, type="non_strategic"
        )
        self.open_group_fleet = self.fleet(
            host_group=self.group, type="non_strategic", open_to_alliance=True
        )

    def test_associate_list_leaves_out_alliance_only_audience(self):
        self.assertEqual(
            self.listed_ids(self.outsider),
            {
                self.open_fleet.id,
                self.associate_fleet.id,
                self.open_group_fleet.id,
            },
        )

    def test_alliance_list_leaves_out_associate_only_audience(self):
        self.assertEqual(
            self.listed_ids(self.alliance_pilot),
            {
                self.open_fleet.id,
                self.alliance_fleet.id,
                self.open_group_fleet.id,
            },
        )

    def test_group_member_also_sees_members_only_group_fleet(self):
        self.assertEqual(
            self.listed_ids(self.member),
            {
                self.open_fleet.id,
                self.associate_fleet.id,
                self.members_only.id,
                self.open_group_fleet.id,
            },
        )

    def test_legacy_permission_still_sees_every_audience(self):
        # can_use_feature falls back to fleets.view_evefleet, so the
        # detail endpoint shows these fleets; the list must too.
        self.outsider.user_permissions.add(
            Permission.objects.get(codename="view_evefleet")
        )
        self.outsider = User.objects.get(pk=self.outsider.pk)
        listed = self.listed_ids(self.outsider)
        self.assertIn(self.alliance_fleet.id, listed)
        self.assertIn(self.associate_fleet.id, listed)
        self.assertNotIn(self.members_only.id, listed)

    def test_creator_sees_own_fleet_outside_its_audience(self):
        own = self.fleet(
            audience=self.alliance_audience, created_by=self.outsider
        )
        self.assertIn(own.id, self.listed_ids(self.outsider))
        self.assertEqual(
            self.call(f"/{own.id}", self.outsider).status_code, 200
        )

    def test_on_leave_member_list_matches_detail(self):
        # On leave is a community status: it swaps the pilot's affiliation
        # group for the On Leave group; their tribe membership stays.
        on_leave = self._pilot("on_leave_member", self.alliance)
        add_member(self.group, on_leave)
        UserCommunityStatus.objects.create(
            user=on_leave, status=UserCommunityStatus.STATUS_ON_LEAVE
        )
        on_leave.groups.remove(self.alliance.group)
        response = self.call("/v3?fleet_filter=upcoming", on_leave)
        listed = (
            {fleet["id"] for fleet in response.json()}
            if response.status_code == 200
            else set()
        )
        for fleet in (
            self.open_fleet,
            self.alliance_fleet,
            self.associate_fleet,
            self.members_only,
            self.open_group_fleet,
        ):
            with self.subTest(fleet=fleet.audience or fleet.host_group):
                detail = self.call(f"/{fleet.id}", on_leave).status_code
                self.assertEqual(fleet.id in listed, detail == 200)

    def test_list_matches_detail_for_every_pilot_and_fleet(self):
        fleets = [
            self.open_fleet,
            self.alliance_fleet,
            self.associate_fleet,
            self.members_only,
            self.open_group_fleet,
        ]
        for user in (self.alliance_pilot, self.member, self.outsider):
            listed = self.listed_ids(user)
            for fleet in fleets:
                with self.subTest(user=user.username, fleet=fleet.audience):
                    detail = self.call(f"/{fleet.id}", user).status_code
                    self.assertEqual(
                        fleet.id in listed,
                        detail == 200,
                        f"list and detail disagree (detail {detail})",
                    )


class FleetFormReferenceDataTests(FleetAudienceTestBase):
    GROUP_TYPES = ["non_strategic", "training", "npsi"]

    def test_group_publisher_without_fleets_create_loads_the_form(self):
        self.group.fleet_policy = TribeGroup.POLICY_MEMBERS
        self.group.save()

        types = self.call("/types", self.member)
        self.assertEqual(types.status_code, 200, types.content)
        self.assertEqual(types.json(), self.GROUP_TYPES)

        locations = self.call("/v2/locations", self.member)
        self.assertEqual(locations.status_code, 200, locations.content)
        self.assertEqual(
            [row["location_id"] for row in locations.json()], [123]
        )

    def test_member_the_policy_does_not_allow_is_still_denied(self):
        # The group's default policy is chiefs only.
        for path in ("/types", "/v2/locations"):
            with self.subTest(path=path):
                self.assertEqual(self.call(path, self.member).status_code, 403)

    def test_audiences_stay_alliance_fleet_only(self):
        self.group.fleet_policy = TribeGroup.POLICY_MEMBERS
        self.group.save()
        self.assertEqual(self.call("/audiences", self.member).status_code, 403)

    def test_fleets_create_keeps_every_type(self):
        types = self.call("/types", self.alliance_pilot)
        self.assertEqual(types.status_code, 200, types.content)
        self.assertEqual(types.json(), ["strategic"] + self.GROUP_TYPES)
