"""Storing requirements, readiness, capabilities and accounts."""

from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.utils import timezone
from eveuniverse.models import EveCategory, EveGroup, EveType

from app.test import TestCase
from capabilities import services, tasks
from capabilities.engine import sde as sde_mod
from capabilities.models import (
    CharacterAccount,
    CharacterAccountLink,
    CharacterCapability,
    CharacterFittingReadiness,
    FittingRequirementSet,
    SdeSnapshot,
)
from capabilities.tests.helpers import (
    all_skills_at,
    fixture_eft,
    fixture_sde,
    fixture_snapshot,
    store_fixture_snapshot,
)
from eveonline.models import EveCharacter, EveCharacterSkill
from fittings.models import (
    EveDoctrine,
    EveDoctrineFitting,
    EveFitting,
    EveFittingHistory,
)
from fleets.models import EveFleetInstance, EveFleetInstanceMember
from fleets.tests import (
    disconnect_fleet_signals,
    make_test_fleet,
    setup_fleet_reference_data,
)

SDE = fixture_sde()
GUARDIAN = 11987


def give_skills(character, skills: dict[int, int]):
    EveCharacterSkill.objects.bulk_create(
        [
            EveCharacterSkill(
                character=character,
                skill_id=s,
                skill_name=SDE.name(s),
                skill_points=0,
                skill_level=lv,
            )
            for s, lv in skills.items()
        ]
    )


class CapabilityServicesTestCase(TestCase):
    def setUp(self):
        super().setUp()
        disconnect_fleet_signals()
        setup_fleet_reference_data()
        store_fixture_snapshot()
        self.doctrine = EveDoctrine.objects.create(
            name="Armor", type="strategic", description=""
        )
        self.guardian = self._fit("guardian", GUARDIAN, "primary")

    def _fit(self, name, ship_id, role, doctrine=None):
        eft = fixture_eft(name)
        fitting = EveFitting.objects.create(
            name=EveFitting.fitting_name_from_eft(eft),
            ship_id=ship_id,
            description="",
            eft_format=eft,
        )
        EveDoctrineFitting.objects.create(
            doctrine=doctrine or self.doctrine, fitting=fitting, role=role
        )
        return fitting

    def _character(self, character_id, name, skills, user=None):
        character = EveCharacter.objects.create(
            character_id=character_id,
            character_name=name,
            user=user or self.user,
        )
        give_skills(character, skills)
        return character

    def test_snapshot_round_trip_and_pruning(self):
        snapshot = SdeSnapshot.objects.get(is_current=True)
        self.assertEqual(snapshot.build, fixture_snapshot()["build"])
        self.assertEqual(services.current_sde().build, snapshot.build)
        for build in (1, 2, 3):
            services.store_snapshot({**fixture_snapshot(), "build": build})
        self.assertEqual(SdeSnapshot.objects.count(), services.KEEP_SNAPSHOTS)
        self.assertEqual(SdeSnapshot.objects.get(is_current=True).build, 3)

    def test_recompute_stores_rows_and_skips_unchanged_inputs(self):
        rs = services.recompute_fitting(self.guardian.pk)
        self.assertEqual(rs.capability, "Logistics")
        self.assertTrue(rs.strategic)
        self.assertTrue(
            rs.rows.filter(skill_name="Logistics Cruisers").exists()
        )
        again = services.recompute_fitting(self.guardian.pk)
        self.assertEqual(again.pk, rs.pk)
        forced = services.recompute_fitting(self.guardian.pk, force=True)
        self.assertNotEqual(forced.pk, rs.pk)
        self.assertEqual(
            FittingRequirementSet.objects.filter(
                fitting=self.guardian, is_current=True
            ).count(),
            1,
        )

    def test_capability_override_on_the_fitting(self):
        self.guardian.capability = "Support"
        self.guardian.save(update_fields=["capability"])
        rs = services.recompute_fitting(self.guardian.pk)
        self.assertEqual(rs.capability, "Support")
        self.assertEqual(rs.capability_source, "override")

    def test_not_in_a_doctrine_means_no_requirements(self):
        EveDoctrineFitting.objects.filter(fitting=self.guardian).delete()
        self.assertIsNone(services.recompute_fitting(self.guardian.pk))

    def test_strategic_needs_core_non_strategic_needs_hard(self):
        fit = self.guardian
        hard_only = all_skills_at(SDE, 5)
        hard_only[SDE.resolve("Capacitor Management")] = 0
        pilot = self._character(2001, "Hard Only", hard_only)
        services.recompute_all_requirements()
        services.refresh_readiness()
        row = CharacterFittingReadiness.objects.get(
            character=pilot, fitting=fit
        )
        self.assertTrue(row.hard_ready)
        self.assertFalse(row.core_ready)
        self.assertFalse(row.doctrine_ready)

        self.doctrine.type = "non_strategic"
        self.doctrine.save()
        services.recompute_all_requirements()
        services.refresh_readiness()
        row.refresh_from_db()
        self.assertTrue(row.doctrine_ready)

    def test_capabilities_unlocked_ready_and_proven(self):
        pilot = self._character(2002, "Logi", all_skills_at(SDE, 5))
        newbie = self._character(2003, "New", {})
        services.recompute_all_requirements()
        services.refresh_readiness()
        services.refresh_capabilities()
        logi = CharacterCapability.objects.get(
            character=pilot, capability="Logistics"
        )
        self.assertEqual(logi.level, CharacterCapability.LEVEL_DOCTRINE_READY)
        self.assertEqual(logi.best_fitting, self.guardian)
        self.assertEqual(
            CharacterCapability.objects.get(
                character=newbie, capability="Logistics"
            ).level,
            CharacterCapability.LEVEL_NONE,
        )

        fc = User.objects.create(username="fc")
        for n in range(3):
            fleet = make_test_fleet(f"Fleet {n}", fc)
            instance = EveFleetInstance.objects.create(
                id=9000 + n, eve_fleet=fleet
            )
            self._seat(instance, pilot, GUARDIAN)
        services.refresh_capabilities()
        logi.refresh_from_db()
        self.assertEqual(logi.level, CharacterCapability.LEVEL_PROVEN)
        self.assertEqual(logi.fleets_365d, 3)

    def _seat(self, instance, character, hull, start=None, minutes=60):
        start = start or timezone.now() - timedelta(hours=2)
        member = EveFleetInstanceMember.objects.create(
            eve_fleet_instance=instance,
            character_id=character.character_id,
            character_name=character.character_name,
            role="squad_member",
            role_name="Squad Member",
            ship_type_id=hull,
            ship_name=SDE.name(hull),
            solar_system_id=30002537,
            solar_system_name="Amamake",
            squad_id=1,
            wing_id=1,
        )
        EveFleetInstanceMember.objects.filter(pk=member.pk).update(
            join_time=start, updated_at=start + timedelta(minutes=minutes)
        )
        return member

    def test_account_links_need_real_overlap(self):
        main = self._character(2010, "Main", {})
        alt = self._character(2011, "Alt", {})
        swap = self._character(2012, "Same Account", {})
        fc = User.objects.create(username="fc2")
        fleet = make_test_fleet("Fleet", fc)
        instance = EveFleetInstance.objects.create(id=9100, eve_fleet=fleet)
        start = timezone.now() - timedelta(hours=3)
        self._seat(instance, main, GUARDIAN, start=start, minutes=120)
        self._seat(instance, alt, GUARDIAN, start=start + timedelta(minutes=5))
        # Logs in a few minutes before Main's last poll: an account swap.
        self._seat(
            instance, swap, GUARDIAN, start=start + timedelta(minutes=115)
        )
        services.refresh_account_links()
        pairs = {
            frozenset((link.character_a_id, link.character_b_id))
            for link in CharacterAccountLink.objects.all()
        }
        self.assertIn(frozenset((main.pk, alt.pk)), pairs)
        self.assertNotIn(frozenset((main.pk, swap.pk)), pairs)
        accounts = CharacterAccount.objects.filter(user=self.user)
        self.assertEqual(accounts.count(), 2)

    def test_group_accounts_keeps_linked_characters_apart(self):
        links = {
            frozenset((1, 2)): 50,
            frozenset((1, 3)): 40,
            frozenset((2, 3)): 30,
            frozenset((1, 4)): 2,
        }
        accounts = services.group_accounts([1, 2, 3, 4, 5], links)
        self.assertEqual(len(accounts), 3)
        for account in accounts:
            for a in account:
                for b in account:
                    self.assertNotIn(frozenset((a, b)), links)
        self.assertNotIn(5, [c for a in accounts for c in a])

    def test_character_task_refreshes_one_character(self):
        pilot = self._character(2020, "Logi", all_skills_at(SDE, 5))
        services.recompute_all_requirements()
        tasks.refresh_character_readiness(pilot.pk)
        self.assertTrue(
            CharacterFittingReadiness.objects.get(
                character=pilot
            ).doctrine_ready
        )
        self.assertEqual(
            CharacterCapability.objects.filter(character=pilot).count(), 8
        )

    def test_fitting_save_queues_a_recompute(self):
        with mock.patch.object(
            tasks.recompute_fitting_requirements, "apply_async"
        ) as apply_async, self.captureOnCommitCallbacks(execute=True):
            self.guardian.description = "updated"
            self.guardian.save()
        apply_async.assert_called_once()
        self.assertEqual(
            apply_async.call_args.kwargs["args"], [self.guardian.pk]
        )

    def test_override_change_is_versioned(self):
        category, _ = EveCategory.objects.get_or_create(
            id=16, defaults={"name": "Skill", "published": True}
        )
        group, _ = EveGroup.objects.get_or_create(
            id=1210,
            defaults={
                "name": "Targeting",
                "published": True,
                "eve_category": category,
            },
        )
        skill = EveType.objects.create(
            id=SDE.resolve("Signature Analysis"),
            name="Signature Analysis",
            published=True,
            eve_group=group,
        )
        version = self.guardian.latest_version
        old = self.guardian.skill_override_snapshot()
        self.guardian.skill_overrides.create(
            skill=skill,
            action="exclude",
            tier="core",
        )
        self.guardian.record_requirement_change("", old)
        self.guardian.refresh_from_db()
        self.assertNotEqual(self.guardian.latest_version, version)
        history = EveFittingHistory.objects.get(superseded_version_id=version)
        self.assertEqual(history.skill_overrides, [])


class SdeUpdateTestCase(TestCase):
    def test_new_build_is_loaded_and_old_build_is_skipped(self):
        store_fixture_snapshot()
        current = fixture_snapshot()["build"]
        with mock.patch.object(
            services, "latest_published_build", return_value=current
        ):
            self.assertIsNone(services.update_sde_if_new())
        newer = {**fixture_snapshot(), "build": current + 1}
        with mock.patch.object(
            services, "latest_published_build", return_value=current + 1
        ), mock.patch.object(services, "download_build"), mock.patch.object(
            sde_mod, "build_snapshot", return_value=newer
        ):
            self.assertEqual(services.update_sde_if_new(), current + 1)
        self.assertEqual(services.current_sde().build, current + 1)

    def test_failed_download_keeps_the_current_build(self):
        store_fixture_snapshot()
        current = fixture_snapshot()["build"]
        with mock.patch.object(
            services, "latest_published_build", return_value=current + 1
        ), mock.patch.object(
            services, "download_build", side_effect=OSError("network")
        ):
            with self.assertRaises(OSError):
                services.update_sde_if_new()
        self.assertEqual(services.current_sde().build, current)
