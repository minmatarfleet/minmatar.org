"""get_user_feature_codes must agree with can_use_feature for every code."""

from django.contrib.auth.models import Group, Permission, User
from django.db.models import signals

from app.test import TestCase
from fleets.models import EveFleet
from groups.features.registry import FEATURE_DEFINITIONS
from groups.helpers.feature_access import (
    can_use_feature,
    clear_feature_cache,
    get_user_feature_codes,
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


def _perm(dotted: str) -> Permission:
    app_label, codename = dotted.split(".")
    return Permission.objects.get(
        content_type__app_label=app_label, codename=codename
    )


class FeatureCodesTestCase(TestCase):
    """Archetype users against real registry wiring."""

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
        self.affiliations = {
            name: AffiliationType.objects.create(
                name=name,
                group=Group.objects.create(name=f"{name} Group"),
                priority=priority,
                default=False,
            )
            for name, priority in (
                ("Alliance", 40),
                ("Associate", 30),
                ("Militia", 20),
                ("Guest", 10),
            )
        }
        self.tech_team = Group.objects.create(name="Technology Team")
        pulse = Tribe.objects.create(name="Pulse", slug="pulse")
        self.thinkspeak = TribeGroup.objects.create(
            tribe=pulse, name="Thinkspeak", code="pulse.thinkspeak"
        )
        supply = Tribe.objects.create(name="Supply", slug="supply")
        self.mining = TribeGroup.objects.create(
            tribe=supply, name="Mining", code="supply.mining"
        )
        self.market = TribeGroup.objects.create(
            tribe=supply, name="Market", code="supply.market"
        )
        clear_feature_cache()
        SyncCommand().handle()
        clear_feature_cache()

    def tearDown(self):
        clear_feature_cache()

    def _user(self, name, affiliation=None, status=None, **kwargs):
        user = User.objects.create_user(username=name, **kwargs)
        if affiliation:
            UserAffiliation.objects.create(
                user=user, affiliation=self.affiliations[affiliation]
            )
        if status:
            UserCommunityStatus.objects.create(user=user, status=status)
        return user

    def _archetypes(self):
        users = [
            self._user("guestless"),
            self._user("inactive", "Alliance", is_active=False),
            self._user(
                "inactive_superuser", is_active=False, is_superuser=True
            ),
            self._user("superuser", is_superuser=True),
        ]
        for name in self.affiliations:
            users.append(self._user(f"aff_{name}", name))
        users.append(self._user("on_leave", "Alliance", status="on_leave"))
        users.append(self._user("trial", "Alliance", status="trial"))

        legacy = self._user("legacy_holder", "Associate", status="on_leave")
        for dotted in {
            d.legacy_permission
            for d in FEATURE_DEFINITIONS.values()
            if d.legacy_permission
        }:
            legacy.user_permissions.add(_perm(dotted))
        users.append(legacy)

        staff = self._user("staff_holder")
        for dotted in {
            d.staff_permission
            for d in FEATURE_DEFINITIONS.values()
            if d.staff_permission
        }:
            staff.user_permissions.add(_perm(dotted))
        users.append(staff)

        group_perm = self._user("group_perm_holder", "Militia")
        group_perm.groups.add(self.affiliations["Militia"].group)
        self.affiliations["Militia"].group.permissions.add(
            _perm("fleets.manage_any_fleet"),
            _perm("eveonline.add_evecharactertag"),
        )
        users.append(group_perm)

        tech = self._user("tech", "Guest", status="on_leave")
        tech.groups.add(self.tech_team)
        users.append(tech)

        thinker = self._user("thinker", "Associate")
        TribeGroupMembership.objects.create(
            user=thinker,
            tribe_group=self.thinkspeak,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        TribeGroupMembership.objects.create(
            user=thinker,
            tribe_group=self.market,
            status="pending",
        )
        users.append(thinker)

        group_chief = self._user("group_chief", "Alliance")
        self.mining.chief = group_chief
        self.mining.save()
        users.append(group_chief)

        tribe_chief = self._user("tribe_chief", "Alliance")
        self.mining.tribe.chief = tribe_chief
        self.mining.tribe.save()
        users.append(tribe_chief)
        return users

    def test_matches_can_use_feature_for_every_code(self):
        for user in self._archetypes():
            expected = [
                code
                for code in sorted(FEATURE_DEFINITIONS)
                if can_use_feature(user, code)
            ]
            with self.subTest(user=user.username):
                self.assertEqual(get_user_feature_codes(user), expected)

    def test_matches_with_missing_and_inactive_rows(self):
        users = self._archetypes()
        PilotFeature.objects.filter(code="fleets.view").delete()
        PilotFeature.objects.filter(code="tribes.roster.view").update(
            is_active=False
        )
        clear_feature_cache()
        for user in users:
            expected = [
                code
                for code in sorted(FEATURE_DEFINITIONS)
                if can_use_feature(user, code)
            ]
            with self.subTest(user=user.username):
                self.assertEqual(get_user_feature_codes(user), expected)

    def test_superuser_gets_every_code(self):
        user = self._user("root", is_superuser=True)
        self.assertEqual(
            get_user_feature_codes(user), sorted(FEATURE_DEFINITIONS)
        )

    def test_inactive_and_anonymous_get_nothing(self):
        self.assertEqual(get_user_feature_codes(None), [])
        user = self._user("gone", "Alliance", is_active=False)
        self.assertEqual(get_user_feature_codes(user), [])

    def test_new_site_gates_keep_todays_audience(self):
        """Unwired, legacy-backed codes grant exactly the old permission."""
        alliance = self._user("plain_alliance", "Alliance")
        holder = self._user("tag_holder", "Guest")
        holder.user_permissions.add(_perm("eveonline.add_evecharactertag"))

        for code in (
            "tribes.roster.view",
            "industry.industrialists.view",
            "characters.readiness",
        ):
            with self.subTest(code=code):
                self.assertNotIn(code, get_user_feature_codes(alliance))
                self.assertIn(code, get_user_feature_codes(holder))

        for code in (
            "surveys.results.view",
            "site.debug_pages",
            "characters.lookup",
        ):
            with self.subTest(code=code):
                staff = self._user(f"staff_{code}", "Alliance")
                staff.groups.add(self.tech_team)
                self.assertNotIn(code, get_user_feature_codes(staff))

    def test_content_manage_follows_thinkspeak_membership(self):
        member = self._user("ts_member", "Guest", status="on_leave")
        TribeGroupMembership.objects.create(
            user=member,
            tribe_group=self.thinkspeak,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        applicant = self._user("ts_applicant", "Alliance")
        TribeGroupMembership.objects.create(
            user=applicant,
            tribe_group=self.thinkspeak,
            status="pending",
        )
        self.assertIn("content.manage", get_user_feature_codes(member))
        self.assertNotIn("content.manage", get_user_feature_codes(applicant))

    def test_lookups_are_loaded_once(self):
        user = self._user("busy", "Alliance", status="trial")
        user.groups.add(self.tech_team)
        TribeGroupMembership.objects.create(
            user=user,
            tribe_group=self.thinkspeak,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        get_user_feature_codes(user)  # warm the feature row cache
        user = User.objects.get(pk=user.pk)
        # affiliation, community status, auth groups, active memberships,
        # chiefships, user permissions, group permissions.
        with self.assertNumQueries(7):
            get_user_feature_codes(user)

    def test_lookups_are_not_memoized_outside_a_batch(self):
        user = self._user("changing", "Guest")
        self.assertFalse(can_use_feature(user, "fleets.create"))
        UserAffiliation.objects.filter(user=user).update(
            affiliation=self.affiliations["Alliance"]
        )
        self.assertTrue(can_use_feature(user, "fleets.create"))
