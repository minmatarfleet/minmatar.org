"""Tests for PilotFeature access evaluation."""

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db.models import signals

from app.test import TestCase
from fleets.models import EveFleet, EveFleetAudience
from groups.helpers.feature_access import (
    can_use_feature,
    clear_feature_cache,
    require_feature,
)
from groups.management.commands.sync_pilot_features import (
    Command as SyncCommand,
)
from groups.models import AffiliationType, PilotFeature, UserAffiliation
from tribes.models import Tribe, TribeGroup, TribeGroupMembership


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
