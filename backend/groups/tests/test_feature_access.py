"""Tests for PilotFeature access evaluation."""

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db.models import signals

from app.test import TestCase
from fleets.models import EveFleet, EveFleetAudience
from groups.features.registry import FEATURE_DEFINITIONS
from groups.helpers.feature_access import (
    can_use_feature,
    clear_feature_cache,
    require_feature,
)
from groups.management.commands.sync_pilot_features import (
    Command as SyncCommand,
)
from groups.models import (
    AffiliationType,
    PilotFeature,
    UserAffiliation,
    UserCommunityStatus,
)
from tribes.models import Tribe, TribeGroup, TribeGroupMembership
from tribes.models import TribeGroupChief
from users.helpers import get_user_permissions


class FeatureAccessTestCase(TestCase):
    def setUp(self):
        signals.post_save.disconnect(
            sender=Group,
            dispatch_uid="group_post_save",
        )
        signals.m2m_changed.disconnect(
            sender=User.groups.through,
            dispatch_uid="user_group_changed",
        )
        signals.post_save.disconnect(
            sender=EveFleet,
            dispatch_uid="update_fleet_schedule_on_save",
        )
        clear_feature_cache()
        SyncCommand().handle()

    def tearDown(self):
        clear_feature_cache()

    def _alliance_affiliation(self):
        group = Group.objects.create(name="Alliance Test")
        return AffiliationType.objects.create(
            name="Alliance",
            group=group,
            priority=10,
            default=False,
        )

    def test_legacy_permission_grants_access(self):
        user = User.objects.create_user(username="legacy_user")
        content_type = ContentType.objects.get(
            app_label="tribes", model="tribegroupmembership"
        )
        perm = Permission.objects.get(
            codename="add_tribegroupmembership", content_type=content_type
        )
        user.user_permissions.add(perm)
        feature = PilotFeature.objects.get(code="tribes.apply")
        feature.affiliations.clear()
        clear_feature_cache()
        self.assertTrue(can_use_feature(user, "tribes.apply"))

    def test_affiliation_wiring_grants_without_legacy(self):
        user = User.objects.create_user(username="aff_user")
        affiliation = self._alliance_affiliation()
        UserAffiliation.objects.create(user=user, affiliation=affiliation)
        feature = PilotFeature.objects.get(code="fleets.create")
        feature.affiliations.set([affiliation])
        clear_feature_cache()
        self.assertTrue(can_use_feature(user, "fleets.create"))

    def test_profile_lists_campaign_view_for_alliance_member(self):
        user = User.objects.create_user(username="campaign_member")
        affiliation = self._alliance_affiliation()
        UserAffiliation.objects.create(user=user, affiliation=affiliation)
        feature = PilotFeature.objects.get(code="campaigns.view")
        feature.affiliations.set([affiliation])
        clear_feature_cache()

        self.assertFalse(user.has_perm("campaigns.view_campaign"))
        self.assertIn("campaigns.view_campaign", get_user_permissions(user.id))

    def test_profile_hides_campaign_view_when_on_leave(self):
        user = User.objects.create_user(username="campaign_leave")
        affiliation = self._alliance_affiliation()
        UserAffiliation.objects.create(user=user, affiliation=affiliation)
        UserCommunityStatus.objects.create(
            user=user, status=UserCommunityStatus.STATUS_ON_LEAVE
        )
        feature = PilotFeature.objects.get(code="campaigns.view")
        feature.affiliations.set([affiliation])
        clear_feature_cache()

        self.assertNotIn(
            "campaigns.view_campaign", get_user_permissions(user.id)
        )

    def test_profile_lists_fleets_view_for_wired_affiliation(self):
        # fleets.view is resource_match: without a fleet it is the
        # affiliation check, and the Fleets pages gate on it.
        user = User.objects.create_user(username="fleet_associate")
        affiliation = self._alliance_affiliation()
        UserAffiliation.objects.create(user=user, affiliation=affiliation)
        feature = PilotFeature.objects.get(code="fleets.view")
        feature.affiliations.set([affiliation])
        clear_feature_cache()

        self.assertFalse(user.has_perm("fleets.view_evefleet"))
        self.assertIn("fleets.view_evefleet", get_user_permissions(user.id))

    def test_profile_hides_fleets_view_from_unwired_affiliation(self):
        user = User.objects.create_user(username="fleet_guest")
        affiliation = self._alliance_affiliation()
        UserAffiliation.objects.create(user=user, affiliation=affiliation)
        PilotFeature.objects.get(code="fleets.view").affiliations.clear()
        clear_feature_cache()

        self.assertNotIn("fleets.view_evefleet", get_user_permissions(user.id))

    def test_profile_does_not_bridge_other_resource_match_features(self):
        user = User.objects.create_user(username="srp_member")
        affiliation = self._alliance_affiliation()
        UserAffiliation.objects.create(user=user, affiliation=affiliation)
        feature = PilotFeature.objects.get(code="srp.submit")
        feature.affiliations.set([affiliation])
        clear_feature_cache()

        legacy = FEATURE_DEFINITIONS["srp.submit"].legacy_permission
        self.assertNotIn(legacy, get_user_permissions(user.id))

    def _freighters(self, *, chief=None, tribe_chief=None):
        tribe = Tribe.objects.create(
            name="Supply", slug="supply-freight", chief=tribe_chief
        )
        group = TribeGroup.objects.create(
            tribe=tribe,
            name="Freighters",
            code="supply.freighters",
        )
        if chief is not None:
            TribeGroupChief.objects.create(
                tribe_group=group, region="US", user=chief
            )
        feature = PilotFeature.objects.get(code="freight.manage")
        feature.tribe_groups.set([group])
        clear_feature_cache()
        return group

    def test_profile_lists_freight_manage_for_group_chief(self):
        # The routes page still gates on this permission in legacy mode.
        chief = User.objects.create_user(username="freighter_chief")
        self._freighters(chief=chief)

        self.assertFalse(chief.has_perm("freight.change_evefreightroute"))
        self.assertIn(
            "freight.change_evefreightroute", get_user_permissions(chief.id)
        )
        self.assertTrue(can_use_feature(chief, "freight.manage"))

    def test_profile_lists_freight_manage_for_tribe_chief(self):
        chief = User.objects.create_user(username="supply_chief")
        self._freighters(tribe_chief=chief)

        self.assertIn(
            "freight.change_evefreightroute", get_user_permissions(chief.id)
        )
        self.assertTrue(can_use_feature(chief, "freight.manage"))

    def test_profile_hides_freight_manage_from_members(self):
        chief = User.objects.create_user(username="freighter_seat")
        member = User.objects.create_user(username="freighter_member")
        group = self._freighters(chief=chief)
        TribeGroupMembership.objects.create(
            user=member,
            tribe_group=group,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )

        self.assertNotIn(
            "freight.change_evefreightroute", get_user_permissions(member.id)
        )
        self.assertFalse(can_use_feature(member, "freight.manage"))

    def test_profile_hides_freight_manage_when_chief_on_leave(self):
        chief = User.objects.create_user(username="freighter_leave")
        self._freighters(chief=chief)
        UserCommunityStatus.objects.create(
            user=chief, status=UserCommunityStatus.STATUS_ON_LEAVE
        )

        self.assertNotIn(
            "freight.change_evefreightroute", get_user_permissions(chief.id)
        )
        self.assertFalse(can_use_feature(chief, "freight.manage"))

    def test_profile_does_not_bridge_other_tribe_membership_screens(self):
        user = User.objects.create_user(username="miner_member")
        tribe = Tribe.objects.create(name="Supply Mining", slug="supply-m")
        group = TribeGroup.objects.create(
            tribe=tribe, name="Mining", code="supply.mining"
        )
        feature = PilotFeature.objects.get(code="buyback.manage")
        feature.tribe_groups.set([group])
        clear_feature_cache()
        TribeGroupMembership.objects.create(
            user=user,
            tribe_group=group,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )

        self.assertNotIn(
            "buyback.change_evebuybacksettings",
            get_user_permissions(user.id),
        )

    def test_denied_without_scope_or_legacy(self):
        user = User.objects.create_user(username="denied_user")
        feature = PilotFeature.objects.get(code="fleets.create")
        feature.affiliations.clear()
        clear_feature_cache()
        self.assertFalse(can_use_feature(user, "fleets.create"))

    def test_superuser_always_allowed(self):
        user = User.objects.create_superuser(
            username="admin", email="", password="x"
        )
        self.assertTrue(can_use_feature(user, "fleets.create"))

    def test_tribe_group_target_requires_affiliation(self):
        user = User.objects.create_user(username="apply_user")
        affiliation = self._alliance_affiliation()
        UserAffiliation.objects.create(user=user, affiliation=affiliation)
        tribe = Tribe.objects.create(name="Industry", slug="industry")
        tribe_group = TribeGroup.objects.create(
            tribe=tribe, name="Mining", code="industry.mining"
        )
        feature = PilotFeature.objects.get(code="tribes.apply")
        feature.affiliations.set([affiliation])
        feature.tribe_groups.set([tribe_group])
        clear_feature_cache()
        self.assertTrue(
            can_use_feature(user, "tribes.apply", tribe_group=tribe_group)
        )

    def _affiliation(self, name: str, priority: int):
        group = Group.objects.create(name=f"{name} Test {priority}")
        return AffiliationType.objects.create(
            name=name,
            group=group,
            priority=priority,
            default=False,
        )

    def test_tribe_group_allowed_affiliations_override(self):
        alliance = self._affiliation("Alliance", 30)
        associate = self._affiliation("Associate", 20)
        militia = self._affiliation("Militia", 10)
        tribe = Tribe.objects.create(name="Capitals", slug="capitals")
        dreads = TribeGroup.objects.create(
            tribe=tribe, name="Dreads", code="capitals.dreads"
        )
        mining = TribeGroup.objects.create(
            tribe=tribe, name="Mining", code="supply.mining-test"
        )
        feature = PilotFeature.objects.get(code="tribes.apply")
        feature.affiliations.set([alliance, associate])
        feature.tribe_groups.clear()
        feature.legacy_permission = ""
        feature.save(update_fields=["legacy_permission"])
        dreads.allowed_affiliations.set([alliance])
        mining.allowed_affiliations.set([associate, militia])
        clear_feature_cache()

        alliance_user = User.objects.create_user(username="alliance_pilot")
        UserAffiliation.objects.create(
            user=alliance_user, affiliation=alliance
        )
        associate_user = User.objects.create_user(username="associate_pilot")
        UserAffiliation.objects.create(
            user=associate_user, affiliation=associate
        )
        militia_user = User.objects.create_user(username="militia_pilot")
        UserAffiliation.objects.create(user=militia_user, affiliation=militia)

        self.assertTrue(
            can_use_feature(alliance_user, "tribes.apply", tribe_group=dreads)
        )
        self.assertFalse(
            can_use_feature(associate_user, "tribes.apply", tribe_group=dreads)
        )
        self.assertFalse(
            can_use_feature(militia_user, "tribes.apply", tribe_group=dreads)
        )
        self.assertTrue(
            can_use_feature(associate_user, "tribes.apply", tribe_group=mining)
        )
        self.assertTrue(
            can_use_feature(militia_user, "tribes.apply", tribe_group=mining)
        )
        self.assertFalse(
            can_use_feature(alliance_user, "tribes.apply", tribe_group=mining)
        )

    def test_tribe_group_empty_allowed_affiliations_inherits_feature(self):
        alliance = self._affiliation("Alliance", 31)
        associate = self._affiliation("Associate", 21)
        militia = self._affiliation("Militia", 11)
        tribe = Tribe.objects.create(name="Pulse", slug="pulse-aff")
        tribe_group = TribeGroup.objects.create(
            tribe=tribe, name="Thinkspeak", code="pulse.thinkspeak-aff"
        )
        feature = PilotFeature.objects.get(code="tribes.apply")
        feature.affiliations.set([alliance, associate])
        feature.tribe_groups.clear()
        feature.legacy_permission = ""
        feature.save(update_fields=["legacy_permission"])
        clear_feature_cache()

        militia_user = User.objects.create_user(username="militia_inherit")
        UserAffiliation.objects.create(user=militia_user, affiliation=militia)
        associate_user = User.objects.create_user(username="associate_inherit")
        UserAffiliation.objects.create(
            user=associate_user, affiliation=associate
        )

        self.assertFalse(
            can_use_feature(
                militia_user, "tribes.apply", tribe_group=tribe_group
            )
        )
        self.assertTrue(
            can_use_feature(
                associate_user, "tribes.apply", tribe_group=tribe_group
            )
        )

    def test_tribe_group_target_ignores_feature_tribe_group_wiring(self):
        user = User.objects.create_user(username="unwired_apply_user")
        alliance = self._affiliation("Alliance", 32)
        UserAffiliation.objects.create(user=user, affiliation=alliance)
        tribe = Tribe.objects.create(name="Pulse", slug="pulse-unwired")
        wired_group = TribeGroup.objects.create(
            tribe=tribe, name="Wired", code="pulse.wired"
        )
        unwired_group = TribeGroup.objects.create(
            tribe=tribe, name="Unwired", code="pulse.unwired"
        )
        feature = PilotFeature.objects.get(code="tribes.apply")
        feature.affiliations.set([alliance])
        feature.tribe_groups.set([wired_group])
        feature.legacy_permission = ""
        feature.save(update_fields=["legacy_permission"])
        clear_feature_cache()

        self.assertTrue(
            can_use_feature(user, "tribes.apply", tribe_group=unwired_group)
        )

    def test_tribe_chief_scope(self):
        user = User.objects.create_user(username="chief_user")
        tribe = Tribe.objects.create(
            name="Industry", slug="industry", chief=user
        )
        tribe_group = TribeGroup.objects.create(
            tribe=tribe, name="Mining", code="industry.mining"
        )
        feature = PilotFeature.objects.get(code="industry.order.submit")
        feature.tribe_groups.set([tribe_group])
        clear_feature_cache()
        self.assertTrue(can_use_feature(user, "industry.order.submit"))

    def test_resource_match_with_audience_groups(self):
        user = User.objects.create_user(username="fleet_user")
        affiliation = self._alliance_affiliation()
        UserAffiliation.objects.create(user=user, affiliation=affiliation)
        user.groups.add(affiliation.group)
        audience = EveFleetAudience.objects.create(name="Test Audience")
        audience.groups.add(affiliation.group)
        fleet = EveFleet.objects.create(
            audience=audience,
            type="strat",
            description="test",
            start_time="2026-01-01T00:00:00Z",
        )
        feature = PilotFeature.objects.get(code="fleets.view")
        feature.affiliations.set([affiliation])
        clear_feature_cache()
        self.assertTrue(can_use_feature(user, "fleets.view", fleet=fleet))

    def test_require_feature_returns_403_tuple(self):
        user = User.objects.create_user(username="blocked")
        denied = require_feature(user, "fleets.create")
        self.assertEqual(denied[0], 403)
        self.assertEqual(denied[1]["detail"], "feature_denied")

    def test_sync_preserves_admin_affiliation_wiring(self):
        affiliation = self._alliance_affiliation()
        feature = PilotFeature.objects.get(code="fleets.create")
        feature.affiliations.set([affiliation])
        SyncCommand().handle()
        feature.refresh_from_db()
        self.assertEqual(
            list(feature.affiliations.values_list("pk", flat=True)),
            [affiliation.pk],
        )

    def test_inactive_user_denied(self):
        user = User.objects.create_user(username="inactive", is_active=False)
        self.assertFalse(can_use_feature(user, "fleets.create"))

    def test_tribe_membership_wiring_change_updates_cache(self):
        user = User.objects.create_user(username="thinkspeak_user")
        tribe = Tribe.objects.create(name="Pulse", slug="pulse")
        tribe_group = TribeGroup.objects.create(
            tribe=tribe, name="Thinkspeak", code="pulse.thinkspeak"
        )
        TribeGroupMembership.objects.create(
            user=user,
            tribe_group=tribe_group,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        feature = PilotFeature.objects.get(code="creators.connect")
        feature.tribe_groups.clear()
        clear_feature_cache()
        self.assertFalse(can_use_feature(user, "creators.connect"))
        feature.tribe_groups.set([tribe_group])
        self.assertTrue(can_use_feature(user, "creators.connect"))

    def test_unknown_feature_checks_registry_legacy(self):
        user = User.objects.create_user(username="unknown_perm_user")
        content_type = ContentType.objects.get(
            app_label="fleets", model="evefleet"
        )
        perm = Permission.objects.get(
            codename="view_evefleet", content_type=content_type
        )
        user.user_permissions.add(perm)
        PilotFeature.objects.filter(code="fleets.view").delete()
        clear_feature_cache()
        self.assertTrue(can_use_feature(user, "fleets.view"))
