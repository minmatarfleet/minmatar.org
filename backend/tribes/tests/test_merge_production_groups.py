"""Capital and subcapital production become one Production group."""

import importlib
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.db.models import signals as django_signals
from django.test import TestCase
from django.utils import timezone

from discord.models import DiscordRole
from discord.signals import (
    group_post_save,
    resolve_existing_discord_role_from_server,
    user_group_changed,
)
from eveonline.models import EveCharacter, EveLocation, EvePlayer
from fleets.models import EveFleet, EveFleetInviteWave
from groups.features.types import FeatureScope
from groups.models import PilotFeature
from help_tickets.models import HelpRequestCategory
from industry.models import IndustryOrder
from industry.signals import notify_when_order_tribe_groups_added
from posts.models import EvePost
from structures.models import LocationAudienceGroup, LocationSubmission
from taskboard.models import Project, Task
from tribes.helpers.merge_production_groups import (
    CAPITAL_AUTH,
    NEW_CODE,
    NEW_NAME,
    PRODUCTION_AUTH,
    PRODUCTION_DESCRIPTION,
    SEED_DESCRIPTIONS,
    SUBCAP_AUTH,
    merge_production_groups,
)
from tribes.models import (
    Tribe,
    TribeEvent,
    TribeGroup,
    TribeGroupChief,
    TribeGroupInvitation,
    TribeGroupMembership,
    TribeGroupMembershipCharacter,
    TribeGroupMembershipCharacterHistory,
    TribeGroupMembershipHistory,
    TribeGroupRequirement,
)

ACTIVE = TribeGroupMembership.STATUS_ACTIVE
PENDING = TribeGroupMembership.STATUS_PENDING
INACTIVE = TribeGroupMembership.STATUS_INACTIVE


merge_production = importlib.import_module(
    "tribes.migrations.0053_merge_production_groups"
).merge_production


def _seed(fragment):
    return next(text for text in SEED_DESCRIPTIONS if fragment in text)


class MergeProductionGroupsTestCase(TestCase):
    def setUp(self):
        self._restores = []
        pairs = (
            (
                django_signals.m2m_changed,
                user_group_changed,
                {
                    "sender": User.groups.through,
                    "dispatch_uid": "user_group_changed",
                },
            ),
            (
                django_signals.post_save,
                group_post_save,
                {"sender": Group, "dispatch_uid": "group_post_save"},
            ),
            (
                django_signals.pre_save,
                resolve_existing_discord_role_from_server,
                {
                    "sender": DiscordRole,
                    "dispatch_uid": "resolve_existing_discord_role_from_server",
                },
            ),
            (
                django_signals.m2m_changed,
                notify_when_order_tribe_groups_added,
                {"sender": IndustryOrder.tribe_groups.through},
            ),
        )
        for signal, receiver, kwargs in pairs:
            if signal.disconnect(receiver, **kwargs):
                self._restores.append((signal, receiver, kwargs))
        self.addCleanup(self._restore_signals)
        public = patch("eveonline.signals.update_character_public_data")
        public.start()
        self.addCleanup(public.stop)

        self.supply_auth = Group.objects.create(name="Tribe - Supply")
        self.capital_auth = Group.objects.create(name=CAPITAL_AUTH)
        self.subcap_auth = Group.objects.create(name=SUBCAP_AUTH)
        self.supply = Tribe.objects.create(
            name="Supply",
            slug="supply",
            group=self.supply_auth,
        )
        self.capital = TribeGroup.objects.create(
            tribe=self.supply,
            name="Capital Production",
            code="supply.capital-production",
            description=_seed("Bigger hulls"),
            group=self.capital_auth,
            is_active=True,
        )
        self.subcap = TribeGroup.objects.create(
            tribe=self.supply,
            name="Subcapital Production",
            code="supply.subcapital-production",
            description=_seed("Ships are ammo"),
            content="Hangar notes",
            discord_channel_id=999001,
            group=self.subcap_auth,
            is_active=True,
        )
        self._character_ids = iter(range(880001, 880200))

    def _restore_signals(self):
        for signal, receiver, kwargs in self._restores:
            signal.connect(receiver, **kwargs)

    def _user(self, username):
        return User.objects.create(username=username)

    def _membership(self, user, group, status):
        return TribeGroupMembership.objects.create(
            user=user,
            tribe_group=group,
            status=status,
            approved_at=timezone.now() if status == ACTIVE else None,
        )

    def _character(self, user, name):
        return EveCharacter.objects.create(
            character_id=next(self._character_ids),
            character_name=name,
            user=user,
        )

    def _commit(self, membership, character):
        return TribeGroupMembershipCharacter.objects.create(
            membership=membership, character=character
        )

    def test_merges_roster_without_dropping_people(self):
        cap_only = self._user("cap-only")
        sub_only = self._user("sub-only")
        both = self._user("both-groups")
        mixed = self._user("mixed-status")
        pending = self._user("pending-pilot")
        inactive = self._user("inactive-pilot")
        inactive_both = self._user("inactive-both")
        overflow = self._user("overflow-chief")
        role_holder = self._user("role-holder")

        cap_row = self._membership(cap_only, self.capital, ACTIVE)
        sub_row = self._membership(sub_only, self.subcap, ACTIVE)
        both_cap = self._membership(both, self.capital, ACTIVE)
        both_sub = self._membership(both, self.subcap, ACTIVE)
        mixed_cap = self._membership(mixed, self.capital, INACTIVE)
        mixed_sub = self._membership(mixed, self.subcap, ACTIVE)
        pending_row = self._membership(pending, self.subcap, PENDING)
        self._membership(inactive, self.capital, INACTIVE)
        self._membership(inactive_both, self.capital, INACTIVE)
        self._membership(inactive_both, self.subcap, INACTIVE)
        self._membership(overflow, self.subcap, ACTIVE)

        older = timezone.now() - timedelta(days=400)
        newer = timezone.now() - timedelta(days=10)
        TribeGroupMembership.objects.filter(pk=mixed_cap.pk).update(
            created_at=newer
        )
        TribeGroupMembership.objects.filter(pk=mixed_sub.pk).update(
            created_at=older
        )

        cap_char = self._character(cap_only, "Cap Pilot")
        sub_char = self._character(sub_only, "Sub Pilot")
        both_cap_char = self._character(both, "Both Cap")
        both_sub_char = self._character(both, "Both Sub")
        mixed_cap_char = self._character(mixed, "Mixed Cap")
        mixed_sub_char = self._character(mixed, "Mixed Sub")
        self._commit(cap_row, cap_char)
        self._commit(sub_row, sub_char)
        self._commit(both_cap, both_cap_char)
        self._commit(both_sub, both_sub_char)
        self._commit(mixed_cap, mixed_cap_char)
        self._commit(mixed_sub, mixed_sub_char)
        history = TribeGroupMembershipHistory.objects.create(
            membership=mixed_sub,
            from_status=PENDING,
            to_status=ACTIVE,
            reason="approved",
        )
        char_history = TribeGroupMembershipCharacterHistory.objects.create(
            membership=mixed_sub,
            character=mixed_sub_char,
            action="added",
        )

        cap_only.groups.add(self.capital_auth)
        sub_only.groups.add(self.subcap_auth)
        both.groups.add(self.capital_auth, self.subcap_auth)
        mixed.groups.add(self.subcap_auth)
        pending.groups.add(self.subcap_auth)
        inactive.groups.add(self.capital_auth)
        inactive_both.groups.add(self.capital_auth, self.subcap_auth)
        role_holder.groups.add(self.capital_auth)
        role_char = self._character(role_holder, "Role Pilot")
        EvePlayer.objects.create(
            user=role_holder,
            nickname="role-holder",
            primary_character=role_char,
        )

        TribeGroupChief.objects.create(
            tribe_group=self.capital,
            region=TribeGroupChief.REGION_US,
            user=cap_only,
        )
        TribeGroupChief.objects.create(
            tribe_group=self.subcap,
            region=TribeGroupChief.REGION_AU,
            user=overflow,
        )
        TribeGroupChief.objects.create(
            tribe_group=self.subcap,
            region=TribeGroupChief.REGION_EU,
            user=sub_only,
        )
        TribeGroupChief.objects.create(
            tribe_group=self.subcap,
            region=TribeGroupChief.REGION_US,
            user=both,
        )

        cap_requirement = TribeGroupRequirement.objects.create(
            tribe_group=self.capital
        )
        sub_requirement = TribeGroupRequirement.objects.create(
            tribe_group=self.subcap
        )
        event = TribeEvent.objects.create(
            tribe_group=self.subcap,
            title="Build night",
            starts_at=timezone.now(),
        )
        invitation = TribeGroupInvitation.objects.create(
            tribe_group=self.subcap,
            user=pending,
            expires_at=timezone.now() + timedelta(days=7),
            membership=pending_row,
        )
        author = self._user("post-author")
        post = EvePost.objects.create(
            title="Production post",
            seo_description="Hulls",
            slug="production-post",
            content="Ships",
            user=author,
            host_group=self.subcap,
        )
        post.tribe_groups.add(self.subcap)
        fleet = EveFleet.objects.create(
            type="strategic",
            start_time=timezone.now(),
            host_group=self.subcap,
        )
        wave = EveFleetInviteWave.objects.create(
            eve_fleet=fleet,
            number=1,
            tribe_group_ids=[self.subcap.pk, self.capital.pk],
        )
        order = IndustryOrder.objects.create(
            needed_by=timezone.now().date(),
            public_short_code="P01",
        )
        order.tribe_groups.add(self.subcap, self.capital)
        feature = PilotFeature.objects.create(
            code="industry.order.submit.test",
            label="Submit",
            scope=FeatureScope.TRIBE_CHIEF,
        )
        feature.tribe_groups.add(self.subcap, self.capital)
        location = EveLocation.objects.create(
            location_id=770001,
            location_name="Production Fort",
            solar_system_id=30000142,
            solar_system_name="Amamake",
            short_name="PF",
        )
        audience = LocationAudienceGroup.objects.create(
            location=location, tribe_group=self.subcap
        )
        submission = LocationSubmission.objects.create(
            name="Production Fort",
            audience_tribe_group_ids=[self.subcap.pk],
        )
        now = timezone.now()
        task = Task.objects.create(
            kind=Task.KIND_AUTOMATIC,
            rule="tribe-chief",
            source_key=f"tribe_group:{self.subcap.pk}",
            title="Seat a chief",
            user=author,
            team_kind="tribe_group",
            team_id=self.subcap.pk,
            link_url=(
                f"/alliance/tribes/{self.supply.pk}/{self.subcap.pk}/members"
            ),
            opened_at=now,
            last_activity_at=now,
        )
        project = Project.objects.create(
            name="Hull run",
            team_kind="tribe_group",
            team_id=self.subcap.pk,
            link_url=f"/alliance/tribes/{self.supply.pk}/{self.subcap.pk}",
        )
        category = HelpRequestCategory.objects.create(
            title="Production",
            code="supply.subcapital-production",
            tribe_group=self.subcap,
        )

        original_users = {
            cap_only.pk,
            sub_only.pk,
            both.pk,
            mixed.pk,
            pending.pk,
            inactive.pk,
            inactive_both.pk,
            overflow.pk,
        }
        lines = merge_production_groups(apps)
        self.assertTrue(any("Deleted folded group" in line for line in lines))

        group = TribeGroup.objects.get(code=NEW_CODE)
        self.assertEqual(group.pk, self.capital.pk)
        self.assertEqual(group.name, NEW_NAME)
        self.assertEqual(group.description, PRODUCTION_DESCRIPTION)
        self.assertIn("Hangar notes", group.content)
        self.assertEqual(group.discord_channel_id, 999001)
        self.assertEqual(
            group.group_id, Group.objects.get(name=PRODUCTION_AUTH).pk
        )
        self.assertFalse(
            TribeGroup.objects.filter(
                code="supply.subcapital-production"
            ).exists()
        )
        self.assertEqual(
            list(
                group.ranks.order_by("sort_order").values_list(
                    "code", flat=True
                )
            ),
            ["capital", "subcapital"],
        )
        self.assertEqual(
            group.ranks.get(code="capital").group_id, self.capital_auth.pk
        )
        self.assertEqual(
            group.ranks.get(code="subcapital").group_id, self.subcap_auth.pk
        )

        rows = {
            row.user_id: row
            for row in TribeGroupMembership.objects.filter(tribe_group=group)
        }
        self.assertTrue(original_users <= set(rows))
        self.assertEqual(rows[cap_only.pk].status, ACTIVE)
        self.assertEqual(rows[cap_only.pk].rank.code, "capital")
        self.assertEqual(rows[sub_only.pk].rank.code, "subcapital")
        self.assertEqual(rows[both.pk].status, ACTIVE)
        self.assertEqual(rows[both.pk].rank.code, "capital")
        self.assertEqual(rows[mixed.pk].status, ACTIVE)
        self.assertEqual(rows[mixed.pk].rank.code, "subcapital")
        self.assertEqual(rows[mixed.pk].created_at, older)
        self.assertEqual(rows[pending.pk].status, PENDING)
        self.assertEqual(rows[pending.pk].rank.code, "subcapital")
        self.assertEqual(rows[inactive.pk].status, INACTIVE)
        self.assertEqual(rows[inactive.pk].rank.code, "capital")
        self.assertEqual(rows[inactive_both.pk].status, INACTIVE)
        self.assertEqual(rows[inactive_both.pk].rank.code, "capital")
        self.assertEqual(rows[overflow.pk].status, ACTIVE)
        self.assertIn(role_holder.pk, rows)
        self.assertEqual(rows[role_holder.pk].status, ACTIVE)
        self.assertEqual(rows[role_holder.pk].rank.code, "capital")

        committed = set(
            TribeGroupMembershipCharacter.objects.filter(
                membership__tribe_group=group
            ).values_list("membership__user_id", "character_id")
        )
        self.assertIn((cap_only.pk, cap_char.pk), committed)
        self.assertIn((sub_only.pk, sub_char.pk), committed)
        self.assertIn((both.pk, both_cap_char.pk), committed)
        self.assertIn((both.pk, both_sub_char.pk), committed)
        self.assertIn((mixed.pk, mixed_cap_char.pk), committed)
        self.assertIn((mixed.pk, mixed_sub_char.pk), committed)
        self.assertIn((role_holder.pk, role_char.pk), committed)
        history.refresh_from_db()
        char_history.refresh_from_db()
        self.assertEqual(history.membership_id, rows[mixed.pk].pk)
        self.assertEqual(char_history.membership_id, rows[mixed.pk].pk)

        seats = TribeGroupChief.objects.filter(tribe_group=group)
        self.assertEqual(seats.count(), 3)
        self.assertEqual(
            set(seats.values_list("user_id", flat=True)),
            {cap_only.pk, sub_only.pk, overflow.pk},
        )
        self.assertFalse(seats.filter(user=both).exists())
        self.assertIn(both.pk, rows)

        self.assertEqual(cap_requirement.tribe_group_id, group.pk)
        cap_requirement.refresh_from_db()
        sub_requirement.refresh_from_db()
        self.assertEqual(cap_requirement.tribe_group_id, group.pk)
        self.assertEqual(sub_requirement.tribe_group_id, group.pk)
        event.refresh_from_db()
        invitation.refresh_from_db()
        self.assertEqual(event.tribe_group_id, group.pk)
        self.assertEqual(invitation.tribe_group_id, group.pk)
        self.assertEqual(invitation.membership_id, pending_row.pk)
        post.refresh_from_db()
        fleet.refresh_from_db()
        self.assertEqual(post.host_group_id, group.pk)
        self.assertEqual(
            list(post.tribe_groups.values_list("pk", flat=True)), [group.pk]
        )
        self.assertEqual(fleet.host_group_id, group.pk)
        wave.refresh_from_db()
        self.assertEqual(wave.tribe_group_ids, [group.pk])
        self.assertEqual(
            list(order.tribe_groups.values_list("pk", flat=True)), [group.pk]
        )
        self.assertEqual(
            list(feature.tribe_groups.values_list("pk", flat=True)), [group.pk]
        )
        audience.refresh_from_db()
        submission.refresh_from_db()
        self.assertEqual(audience.tribe_group_id, group.pk)
        self.assertEqual(submission.audience_tribe_group_ids, [group.pk])
        task.refresh_from_db()
        project.refresh_from_db()
        category.refresh_from_db()
        self.assertEqual(task.team_id, group.pk)
        self.assertEqual(task.source_key, f"tribe_group:{group.pk}")
        self.assertIn(f"/{group.pk}/", task.link_url)
        self.assertEqual(project.team_id, group.pk)
        self.assertIn(f"/{group.pk}", project.link_url)
        self.assertEqual(category.tribe_group_id, group.pk)

        self.assertTrue(cap_only.groups.filter(name=PRODUCTION_AUTH).exists())
        self.assertTrue(
            cap_only.groups.filter(pk=self.capital_auth.pk).exists()
        )
        self.assertFalse(
            cap_only.groups.filter(pk=self.subcap_auth.pk).exists()
        )
        self.assertTrue(sub_only.groups.filter(name=PRODUCTION_AUTH).exists())
        self.assertTrue(
            sub_only.groups.filter(pk=self.subcap_auth.pk).exists()
        )
        self.assertFalse(
            sub_only.groups.filter(pk=self.capital_auth.pk).exists()
        )
        self.assertTrue(both.groups.filter(name=PRODUCTION_AUTH).exists())
        self.assertTrue(both.groups.filter(pk=self.capital_auth.pk).exists())
        self.assertFalse(both.groups.filter(pk=self.subcap_auth.pk).exists())
        self.assertFalse(pending.groups.filter(name=PRODUCTION_AUTH).exists())
        self.assertTrue(pending.groups.filter(pk=self.subcap_auth.pk).exists())
        self.assertFalse(inactive.groups.filter(name=PRODUCTION_AUTH).exists())
        self.assertFalse(
            inactive.groups.filter(pk=self.capital_auth.pk).exists()
        )
        self.assertFalse(
            inactive_both.groups.filter(pk=self.capital_auth.pk).exists()
        )
        self.assertFalse(
            inactive_both.groups.filter(pk=self.subcap_auth.pk).exists()
        )
        self.assertTrue(
            role_holder.groups.filter(name=PRODUCTION_AUTH).exists()
        )
        self.assertTrue(
            role_holder.groups.filter(pk=self.capital_auth.pk).exists()
        )

        before = TribeGroupMembership.objects.filter(tribe_group=group).count()
        merge_production_groups(apps)
        self.assertEqual(
            TribeGroupMembership.objects.filter(tribe_group=group).count(),
            before,
        )
        self.assertEqual(TribeGroup.objects.filter(code=NEW_CODE).count(), 1)
        self.assertEqual(group.ranks.count(), 2)

    def test_legacy_industry_codes_fold_in(self):
        capital = TribeGroup.objects.create(
            tribe=self.supply,
            name="Old Capital",
            code="industry.capital-production",
            description=_seed("Bigger hulls"),
            group=Group.objects.create(name="Legacy Capital"),
        )
        subcap = TribeGroup.objects.create(
            tribe=self.supply,
            name="Old Subcapital",
            code="industry.subcapital-production",
            description=_seed("Ships are ammo"),
            group=Group.objects.create(name="Legacy Subcapital"),
        )
        # The supply-coded groups from setUp would be the survivor. This
        # case is a database that never got the supply rename.
        self.capital.delete()
        self.subcap.delete()
        pilot = self._user("legacy-pilot")
        self._membership(pilot, subcap, ACTIVE)
        other = self._user("legacy-capital")
        self._membership(other, capital, ACTIVE)

        merge_production_groups(apps)

        group = TribeGroup.objects.get(code=NEW_CODE)
        self.assertEqual(group.pk, capital.pk)
        self.assertEqual(
            set(
                TribeGroupMembership.objects.filter(
                    tribe_group=group
                ).values_list("user_id", flat=True)
            ),
            {pilot.pk, other.pk},
        )
        self.assertFalse(
            TribeGroup.objects.filter(
                code="industry.subcapital-production"
            ).exists()
        )

    def test_custom_description_is_kept(self):
        self.capital.description = "We build the hulls that decide wars."
        self.capital.save(update_fields=["description"])
        merge_production_groups(apps)
        group = TribeGroup.objects.get(pk=self.capital.pk)
        self.assertEqual(
            group.description, "We build the hulls that decide wars."
        )
        self.assertIn("Ships are ammo", group.content)

    def test_migration_does_not_merge_during_tests(self):
        merge_production(apps, None)
        self.capital.refresh_from_db()
        self.assertEqual(self.capital.code, "supply.capital-production")

    def test_command_merges_and_can_run_again(self):
        stdout = StringIO()
        call_command("merge_production_groups", stdout=stdout)
        text = stdout.getvalue()
        self.assertIn("Production merge complete.", text)
        self.assertTrue(TribeGroup.objects.filter(code=NEW_CODE).exists())
        again = StringIO()
        call_command("merge_production_groups", stdout=again)
        self.assertIn("Production merge complete.", again.getvalue())
        self.assertEqual(TribeGroup.objects.filter(code=NEW_CODE).count(), 1)
