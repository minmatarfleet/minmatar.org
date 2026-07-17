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
from tribes.models import Tribe, TribeGroup


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
