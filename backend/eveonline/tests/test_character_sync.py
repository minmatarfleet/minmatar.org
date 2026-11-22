"""Character sync: registry, audiences, stamping, scheduler, triggers."""

from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from esi.exceptions import ESIErrorLimitException
from esi.models import Scope, Token
from eveuniverse.models import EveCategory, EveGroup, EveType

from app.test import TestCase
from buyback.models import BUYBACK_CORPORATION_ID
from buyback.tasks import sync_buyback_contracts_task
from eveonline import character_sync as sync
from eveonline import esi_budget
from eveonline.client import EsiResponse, _observed, record_esi_outcomes
from eveonline.models import (
    EveAlliance,
    EveCharacter,
    EveCharacterMiningDelta,
    EveCharacterMiningEntry,
    EveCharacterSkill,
    EveCharacterSyncState,
)
from eveonline.tasks import character_sync as tasks
from eveonline.tasks.corporations import sync_freight_contracts
from eveonline.tasks.characters import (
    fanout_countdown,
    update_alliance_characters,
)
from freight.models import FREIGHT_CORPORATION_ID
from fleets.models import EveFleet, EveFleetInstance, EveFleetInstanceMember
from groups.models import UserCommunityStatus
from industry.models import IndustryOrderItem, IndustryOrderItemAssignment
from industry.test_utils import create_industry_order
from tribes.models import Tribe, TribeGroup, TribeGroupMembership

ALLIANCE_ID = 99011978
ALL_SCOPES = sorted(
    {
        scope
        for section in sync.SECTIONS
        for scopes in section.scopes
        for scope in scopes
    }
)


def make_character(
    character_id, user=None, alliance_id=None, scopes=ALL_SCOPES, **fields
):
    token = Token.objects.create(character_id=character_id, user=user)
    for name in scopes:
        token.scopes.add(Scope.objects.get_or_create(name=name)[0])
    return EveCharacter.objects.create(
        character_id=character_id,
        character_name=f"Pilot {character_id}",
        token=token,
        user=user,
        alliance_id=alliance_id,
        **fields,
    )


def state(character, section):
    return EveCharacterSyncState.objects.get(
        character=character, section=section
    )


class SyncTestCase(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        EveAlliance.objects.create(
            alliance_id=ALLIANCE_ID, name="Minmatar Fleet Alliance"
        )
        self.user = User.objects.create(username="pilot")
        self.main = make_character(
            1001, user=self.user, alliance_id=ALLIANCE_ID
        )
        self.alt = make_character(1002, user=self.user)
        self.outsider = make_character(
            2001, user=User.objects.create(username="outsider")
        )
        # Every section function is a no-op unless a test says otherwise.
        self.runs = []
        patcher = patch.object(
            sync,
            "SECTIONS",
            tuple(
                sync.Section(
                    s.name,
                    s.scopes,
                    self._recorder(s.name),
                    s.interval,
                    s.weight,
                )
                for s in sync.SECTIONS
            ),
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        by_name = patch.object(
            sync, "SECTIONS_BY_NAME", {s.name: s for s in sync.SECTIONS}
        )
        by_name.start()
        self.addCleanup(by_name.stop)
        self.responses = {}
        # Extra work a section does when it runs, by section name.
        self.on_run = {}

    def _recorder(self, name):
        def run(character):
            self.runs.append((character.character_id, name))
            if name in self.on_run:
                self.on_run[name](character)
            code = self.responses.get(name, 0)
            if isinstance(code, BaseException):
                raise code
            EsiResponse(response_code=code)

        return run


class ClassifyTests(TestCase):
    def test_codes(self):
        self.assertEqual(sync.classify([0, 0]), sync.Outcome.OK)
        self.assertEqual(sync.classify([0, 404]), sync.Outcome.FAILED)
        self.assertEqual(sync.classify([0, 503]), sync.Outcome.TRANSIENT)
        self.assertEqual(sync.classify([906]), sync.Outcome.TRANSIENT)
        self.assertEqual(sync.classify([420, 404]), sync.Outcome.ERROR_LIMIT)
        self.assertEqual(sync.classify([904]), sync.Outcome.SUSPENDED)
        self.assertEqual(sync.classify([905]), sync.Outcome.NO_SCOPE)
        self.assertEqual(
            sync.classify([], RuntimeError()), sync.Outcome.TRANSIENT
        )
        self.assertEqual(
            sync.classify([], ESIErrorLimitException(reset=30)),
            sync.Outcome.ERROR_LIMIT,
        )

    def test_recorder_sees_every_response(self):
        EsiResponse(response_code=0)
        with record_esi_outcomes() as codes:
            EsiResponse(response_code=0)
            EsiResponse(response_code=404)
        EsiResponse(response_code=500)
        self.assertEqual(codes, [0, 404])


class StampTests(TestCase):
    def setUp(self):
        super().setUp()
        self.row = EveCharacterSyncState(
            section="assets", next_due_at=timezone.now()
        )
        self.now = timezone.now()

    def test_ok_jitters_within_ten_percent(self):
        sync.stamp(
            self.row, sync.Outcome.OK, timedelta(hours=10), now=self.now
        )
        self.assertEqual(self.row.synced_at, self.now)
        delta = self.row.next_due_at - self.now
        self.assertTrue(timedelta(hours=9) <= delta <= timedelta(hours=11))

    def test_failures_back_off_then_wait_the_interval(self):
        for _ in range(2):
            sync.stamp(
                self.row,
                sync.Outcome.FAILED,
                timedelta(hours=24),
                now=self.now,
                detail="403",
            )
            self.assertEqual(
                self.row.next_due_at, self.now + sync.FAILURE_RETRY
            )
        sync.stamp(
            self.row, sync.Outcome.FAILED, timedelta(hours=24), now=self.now
        )
        self.assertEqual(self.row.next_due_at, self.now + timedelta(hours=24))
        self.assertIsNone(self.row.synced_at)

    def test_transient_retries_soon(self):
        sync.stamp(
            self.row, sync.Outcome.TRANSIENT, timedelta(hours=24), now=self.now
        )
        self.assertEqual(self.row.next_due_at, self.now + sync.TRANSIENT_RETRY)

    def test_no_scope_waits_the_interval(self):
        sync.stamp(
            self.row, sync.Outcome.NO_SCOPE, timedelta(hours=4), now=self.now
        )
        self.assertEqual(self.row.next_due_at, self.now + timedelta(hours=4))
        self.assertEqual(self.row.last_error, "no_scope")


class NextSlotTests(TestCase):
    def test_slot_is_half_to_one_and_a_half_intervals_away(self):
        now = timezone.now()
        interval = timedelta(minutes=10)
        for key in range(1000, 1200):
            gap = sync.next_slot(now, interval, key) - now
            self.assertTrue(interval / 2 <= gap <= interval * 1.5, gap)

    def test_a_pilot_keeps_the_same_offset(self):
        interval = timedelta(minutes=10)
        now = timezone.now()
        first = sync.next_slot(now, interval, 90000001)
        later = sync.next_slot(
            first + timedelta(seconds=1), interval, 90000001
        )
        self.assertEqual((later - first) % interval, timedelta(0))

    def test_pilots_spread_over_the_interval(self):
        now = timezone.now()
        interval = timedelta(minutes=10)
        minutes = {
            int(
                (sync.next_slot(now, interval, key) - now).total_seconds()
                // 60
            )
            for key in range(90000000, 90000050)
        }
        # 50 pilots land in every minute of the ten, not in one burst.
        self.assertGreaterEqual(len(minutes), 10)

    def test_stamp_uses_the_slot_when_given_a_key(self):
        now = timezone.now()
        row = EveCharacterSyncState(section="mining", next_due_at=now)
        interval = timedelta(minutes=10)
        sync.stamp(row, sync.Outcome.OK, interval, now=now, slot_key=1234)
        self.assertEqual(row.next_due_at, sync.next_slot(now, interval, 1234))


class MiningTierTests(SyncTestCase):
    def setUp(self):
        super().setUp()
        category = EveCategory.objects.create(
            id=25, name="Asteroid", published=True
        )
        group = EveGroup.objects.create(
            id=462, name="Veldspar", published=True, eve_category=category
        )
        self.veldspar = EveType.objects.create(
            id=1230, name="Veldspar", published=True, eve_group=group
        )

    def _mined(self, character, days_ago):
        EveCharacterMiningEntry.objects.create(
            character=character,
            eve_type=self.veldspar,
            date=timezone.now().date() - timedelta(days=days_ago),
            quantity=1000,
            solar_system_id=30002537,
        )

    def _delta(self, character, minutes_ago):
        EveCharacterMiningDelta.objects.create(
            character=character,
            eve_type=self.veldspar,
            solar_system_id=30002537,
            quantity=100,
            observed_at=timezone.now() - timedelta(minutes=minutes_ago),
        )

    def _skill(self, character, skill_id):
        EveCharacterSkill.objects.create(
            character=character,
            skill_id=skill_id,
            skill_name="Skill",
            skill_points=1,
            skill_level=1,
        )

    def test_tiers_from_ledger_skills_and_recent_pulls(self):
        hot = self.main
        warm = self.alt
        cool = make_character(1003, user=self.user)
        able = make_character(1004, user=self.user)
        unlikely = make_character(1005, user=self.user)
        unknown = make_character(1006, user=self.user)
        self._delta(hot, minutes_ago=5)
        self._mined(warm, days_ago=1)
        self._mined(cool, days_ago=20)
        self._skill(able, 17940)  # Mining Barge
        self._skill(unlikely, 3300)  # Gunnery
        audiences = sync.load_audiences()
        mining = sync.SECTIONS_BY_NAME["mining"]
        self.assertEqual(
            {
                c.character_id: audiences.interval(mining, c.pk)
                for c in (hot, warm, cool, able, unlikely, unknown)
            },
            {
                1001: sync.MINING_HOT_INTERVAL,
                1002: sync.MINING_WARM_INTERVAL,
                1003: sync.MINING_COOL_INTERVAL,
                1004: timedelta(hours=24),
                1005: sync.MINING_UNLIKELY_INTERVAL,
                # No skills synced: not known to be unable, so the default.
                1006: timedelta(hours=24),
            },
        )

    def test_hot_cools_off_after_the_window(self):
        self._delta(self.main, minutes_ago=40)
        audiences = sync.load_audiences()
        mining = sync.SECTIONS_BY_NAME["mining"]
        self.assertNotIn(self.main.pk, audiences.mining_hot)
        self.assertEqual(
            audiences.interval(mining, self.main.pk), timedelta(hours=24)
        )

    def test_hot_beats_fleet_and_on_leave_only_slows_non_miners(self):
        a = sync.Audiences(
            members={1, 2, 3},
            fleet={1, 2},
            mining_hot={1},
            mining_warm={3},
            on_leave={3},
        )
        mining = sync.SECTIONS_BY_NAME["mining"]
        self.assertEqual(a.interval(mining, 1), sync.MINING_HOT_INTERVAL)
        self.assertEqual(a.interval(mining, 2), sync.FLEET_INTERVAL)
        self.assertEqual(a.interval(mining, 3), sync.MINING_WARM_INTERVAL)
        idle_on_leave = sync.Audiences(members={4}, on_leave={4})
        self.assertEqual(
            idle_on_leave.interval(mining, 4), sync.ON_LEAVE_INTERVAL
        )

    def test_a_pull_that_finds_ore_makes_the_pilot_hot(self):
        sync.run_character_sync(self.main)  # first run: every section
        row = state(self.main, "mining")
        self.assertGreater(
            row.next_due_at - timezone.now(), timedelta(hours=10)
        )
        self.on_run["mining"] = lambda character: self._delta(character, 0)
        sync.run_character_sync(self.main, sections=["mining"], force=True)
        row.refresh_from_db()
        gap = row.next_due_at - timezone.now()
        self.assertLessEqual(gap, sync.MINING_HOT_INTERVAL * 1.5)
        self.assertEqual(
            row.next_due_at,
            sync.next_slot(row.attempted_at, sync.MINING_HOT_INTERVAL, 1001),
        )

    def test_skill_sets_are_cached(self):
        self._skill(self.main, 17940)
        sync.load_audiences()
        self._skill(self.alt, 3300)
        # Cached for an hour: the new skill row isn't read yet.
        self.assertNotIn(self.alt.pk, sync.load_audiences().mining_unlikely)


class AudienceTests(SyncTestCase):
    def test_members_include_alts_but_not_outsiders(self):
        audiences = sync.load_audiences()
        self.assertIn(self.main.pk, audiences.members)
        self.assertIn(self.alt.pk, audiences.members)
        self.assertNotIn(self.outsider.pk, audiences.members)

    def test_interval_priority(self):
        a = sync.Audiences(
            members={1},
            fleet={1},
            contract_owners={1},
            job_assignees={1},
            on_leave={1},
            pi={1},
        )
        s = sync.SECTIONS_BY_NAME
        self.assertEqual(a.interval(s["killmails"], 1), sync.FLEET_INTERVAL)
        self.assertEqual(a.interval(s["contracts"], 1), sync.INDUSTRY_INTERVAL)
        self.assertEqual(
            a.interval(s["industry_jobs"], 1), sync.INDUSTRY_INTERVAL
        )
        self.assertEqual(a.interval(s["assets"], 1), sync.ON_LEAVE_INTERVAL)
        self.assertEqual(a.interval(s["planets"], 1), timedelta(hours=72))
        plain = sync.Audiences(members={2})
        self.assertEqual(plain.interval(s["planets"], 2), timedelta(days=7))
        self.assertEqual(plain.interval(s["assets"], 2), timedelta(hours=4))
        self.assertEqual(plain.interval(s["skills"], 2), timedelta(hours=24))
        leave = sync.Audiences(members={3}, on_leave={3})
        # Longer intervals stay longer than 72 h.
        self.assertEqual(leave.interval(s["planets"], 3), timedelta(days=7))

    def test_industry_audiences_reach_outside_members(self):
        cat = EveCategory.objects.create(id=6, name="Ship", published=True)
        group = EveGroup.objects.create(
            id=25, name="Frigate", published=True, eve_category=cat
        )
        rifter = EveType.objects.create(
            id=587, name="Rifter", published=True, eve_group=group
        )
        order = create_industry_order(
            needed_by=timezone.now().date(), character=self.outsider
        )
        item = IndustryOrderItem.objects.create(
            order=order, eve_type=rifter, quantity=1
        )
        builder = make_character(
            3001, user=User.objects.create(username="builder")
        )
        builder_alt = make_character(3002, user=builder.user)
        IndustryOrderItemAssignment.objects.create(
            order_item=item, character=builder, quantity=1
        )
        audiences = sync.load_audiences()
        self.assertIn(self.outsider.pk, audiences.contract_owners)
        self.assertEqual({builder.pk, builder_alt.pk}, audiences.job_assignees)
        self.assertTrue(audiences.in_scope("contracts", self.outsider.pk))
        self.assertFalse(audiences.in_scope("assets", self.outsider.pk))
        self.assertTrue(audiences.in_scope("industry_jobs", builder_alt.pk))

    @patch("groups.signals.sync_user_community_groups")
    def test_fleet_on_leave_and_pi(self, _):
        fleet = EveFleet.objects.create(
            start_time=timezone.now(),
            type="non_strategic",
            status="active",
            created_by=self.user,
        )
        instance = EveFleetInstance.objects.create(id=1, eve_fleet=fleet)
        EveFleetInstanceMember.objects.create(
            eve_fleet_instance=instance,
            character_id=self.main.character_id,
            character_name="Pilot",
            role="squad_member",
            role_name="Squad Member",
            ship_type_id=587,
            ship_name="Rifter",
            solar_system_id=1,
            solar_system_name="Amamake",
            squad_id=1,
            wing_id=1,
        )
        UserCommunityStatus.objects.create(
            user=self.user, status=UserCommunityStatus.STATUS_ON_LEAVE
        )
        tribe = Tribe.objects.create(name="Supply", slug="supply")
        pi_group = TribeGroup.objects.create(
            tribe=tribe, name="PI", code="supply.planetary-interaction"
        )
        TribeGroupMembership.objects.create(
            user=self.user,
            tribe_group=pi_group,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        audiences = sync.load_audiences()
        self.assertEqual(audiences.fleet, {self.main.pk})
        self.assertEqual(audiences.on_leave, {self.main.pk, self.alt.pk})
        self.assertEqual(audiences.pi, {self.main.pk, self.alt.pk})


class RunCharacterSyncTests(SyncTestCase):
    def test_first_run_forces_every_section_and_stamps(self):
        result = sync.run_character_sync(self.main)
        self.assertEqual(result, {"ok": len(sync.SECTIONS)})
        self.assertEqual(
            [name for _, name in self.runs], [s.name for s in sync.SECTIONS]
        )
        self.assertIsNotNone(state(self.main, "assets").synced_at)

    def test_only_due_sections_run_afterwards(self):
        sync.run_character_sync(self.main)
        self.runs.clear()
        EveCharacterSyncState.objects.filter(
            character=self.main, section="skills"
        ).update(next_due_at=timezone.now() - timedelta(minutes=1))
        sync.run_character_sync(self.main)
        self.assertEqual(self.runs, [(1001, "skills")])

    def test_missing_scope_is_stamped_without_a_call(self):
        token = self.main.token
        token.scopes.remove(Scope.objects.get(name=sync.SCOPE_PLANETS[0]))
        sync.run_character_sync(self.main)
        self.assertNotIn((1001, "planets"), self.runs)
        self.assertEqual(state(self.main, "planets").last_error, "no_scope")

    def test_failed_section_is_stamped_and_the_rest_continue(self):
        self.responses["assets"] = 403
        sync.run_character_sync(self.main)
        row = state(self.main, "assets")
        self.assertIsNone(row.synced_at)
        self.assertEqual(row.consecutive_failures, 1)
        self.assertEqual(row.last_error, "failed 403")
        self.assertIsNotNone(state(self.main, "clones").synced_at)

    def test_transient_stops_the_run(self):
        self.responses["skills"] = 502
        result = sync.run_character_sync(self.main)
        self.assertEqual(result["stopped"], "transient")
        self.assertEqual([name for _, name in self.runs], ["assets", "skills"])
        self.assertFalse(
            EveCharacterSyncState.objects.filter(
                character=self.main, section="killmails"
            ).exists()
        )

    def test_error_limit_stops_without_stamping(self):
        self.responses["skills"] = 420
        result = sync.run_character_sync(self.main)
        self.assertEqual(result["stopped"], "error_limit")
        self.assertFalse(
            EveCharacterSyncState.objects.filter(
                character=self.main, section="skills"
            ).exists()
        )

    def test_paused_budget_runs_nothing(self):
        esi_budget.pause(None, None, 60)
        result = sync.run_character_sync(self.main)
        self.assertEqual(result, {"stopped": "error_limit"})
        self.assertEqual(self.runs, [])

    @patch(
        "eveonline.character_sync.get_esi_downtime_countdown", return_value=60
    )
    def test_downtime_skips(self, _):
        self.assertEqual(
            sync.run_character_sync(self.main), {"skipped": "downtime"}
        )
        self.assertFalse(EveCharacterSyncState.objects.exists())

    def test_running_sync_blocks_a_second_and_marks_forced_sections_due(self):
        sync.run_character_sync(self.main)
        later = timezone.now() + timedelta(hours=1)
        cache.add(f"character-sync:{self.main.pk}", "other", 60)
        result = sync.run_character_sync(
            self.main, sections=["assets"], force=True
        )
        self.assertEqual(result, {"skipped": "running"})
        self.assertLessEqual(state(self.main, "assets").next_due_at, later)
        self.assertLessEqual(
            state(self.main, "assets").next_due_at, timezone.now()
        )


class SchedulerTests(SyncTestCase):
    def setUp(self):
        super().setUp()
        # Past the scheduler's grace period for just-added characters.
        EveCharacter.objects.update(
            created_at=timezone.now() - timedelta(minutes=20)
        )

    def test_just_added_characters_are_left_to_their_first_fetch(self):
        EveCharacter.objects.filter(pk=self.alt.pk).update(
            created_at=timezone.now()
        )
        self.assertNotIn(1002, self.tick().character_ids)

    def tick(self):
        return tasks.plan_tick(sync.load_audiences())

    @override_settings(CHARACTER_SYNC_MODE="fanout")
    def test_fanout_mode_does_nothing(self):
        self.assertEqual(tasks.queue_due_character_syncs(), {"mode": "fanout"})

    def test_new_characters_are_queued_and_leased(self):
        # Members without rows, and the outsider: added recently, never
        # attempted, so its first fetch is retried whatever its scope.
        plan = self.tick()
        self.assertEqual(sorted(plan.character_ids), [1001, 1002, 2001])
        tasks.apply_plan(plan)
        self.assertEqual(
            EveCharacterSyncState.objects.filter(
                queued_at__isnull=False
            ).count(),
            3 * len(sync.SECTIONS),
        )
        # Leased: the next tick picks nobody.
        self.assertEqual(self.tick().character_ids, [])

    def test_tick_spends_its_share_of_the_five_minute_budget(self):
        with override_settings(CHARACTER_SYNC_COST_PER_TICK=300):
            self.assertEqual(tasks.tick_budget(), 60)
        with override_settings(CHARACTER_SYNC_COST_PER_TICK=1):
            self.assertEqual(tasks.tick_budget(), 1)

    def test_budget_limits_the_tick(self):
        with override_settings(CHARACTER_SYNC_COST_PER_TICK=1):
            plan = self.tick()
        # One character always fits, even over budget.
        self.assertEqual(len(plan.character_ids), 1)

    def test_due_rows_oldest_first_and_out_of_scope_pushed(self):
        now = timezone.now()
        for character in (self.main, self.alt):
            sync.run_character_sync(character)
        EveCharacterSyncState.objects.filter(
            character=self.main, section="assets"
        ).update(next_due_at=now - timedelta(minutes=30))
        EveCharacterSyncState.objects.filter(
            character=self.alt, section="assets"
        ).update(next_due_at=now - timedelta(minutes=90))
        stale = EveCharacterSyncState.objects.create(
            character=self.outsider,
            section="assets",
            next_due_at=now - timedelta(days=1),
            attempted_at=now - timedelta(days=1),
        )
        plan = self.tick()
        self.assertEqual(plan.character_ids, [1002, 1001])
        self.assertEqual(plan.out_of_scope_rows, [stale.pk])
        tasks.apply_plan(plan)
        stale.refresh_from_db()
        self.assertGreater(stale.next_due_at, now)

    def test_recent_character_never_attempted_is_retried_whatever_its_scope(
        self,
    ):
        sync.run_character_sync(self.main)
        sync.run_character_sync(self.alt)
        plan = self.tick()
        self.assertEqual(plan.character_ids, [2001])

    @override_settings(CHARACTER_SYNC_MODE="shadow")
    def test_shadow_mode_writes_nothing(self):
        with patch.object(
            tasks.sync_character_sections, "apply_async"
        ) as queue:
            summary = tasks.queue_due_character_syncs()
        queue.assert_not_called()
        self.assertEqual(summary["characters"], 3)
        self.assertFalse(EveCharacterSyncState.objects.exists())

    @override_settings(CHARACTER_SYNC_MODE="scheduled")
    def test_scheduled_mode_queues_spread_across_the_tick(self):
        with patch.object(
            tasks.sync_character_sections, "apply_async"
        ) as queue:
            tasks.queue_due_character_syncs()
        countdowns = [
            call.kwargs["countdown"] for call in queue.call_args_list
        ]
        self.assertEqual(len(countdowns), 3)
        self.assertEqual(countdowns[0], 0)
        self.assertLess(max(countdowns), tasks.TICK_SECONDS)

    @override_settings(CHARACTER_SYNC_MODE="scheduled")
    def test_sync_task_runs_the_character(self):
        result = tasks.sync_character_sections(1001)
        self.assertEqual(result["ok"], len(sync.SECTIONS))


class FanoutTests(SyncTestCase):
    def test_spreads_members_and_skips_recent(self):
        sync.run_character_sync(self.alt)
        with patch(
            "eveonline.tasks.characters.update_character.apply_async"
        ) as queue:
            count = update_alliance_characters()
        self.assertEqual(count, 1)
        kwargs = queue.call_args.kwargs
        self.assertEqual(kwargs["args"], [1001])
        self.assertEqual(kwargs["countdown"], fanout_countdown(1001))
        self.assertEqual(kwargs["expires"], kwargs["countdown"] + 3600)
        self.assertLess(fanout_countdown(1001), 4 * 3600)

    @override_settings(CHARACTER_SYNC_MODE="scheduled")
    def test_scheduled_mode_skips_the_fanout(self):
        with patch(
            "eveonline.tasks.characters.update_character.apply_async"
        ) as queue:
            self.assertEqual(update_alliance_characters(), 0)
        queue.assert_not_called()


class TriggerTests(SyncTestCase):
    def setUp(self):
        super().setUp()
        sync.run_character_sync(self.main)
        sync.run_character_sync(self.alt)

    def test_fleet_join_brings_killmails_and_mining_forward(self):
        fleet = EveFleet.objects.create(
            start_time=timezone.now(),
            type="non_strategic",
            status="active",
            created_by=self.user,
        )
        instance = EveFleetInstance.objects.create(id=2, eve_fleet=fleet)
        EveFleetInstanceMember.objects.create(
            eve_fleet_instance=instance,
            character_id=1001,
            character_name="Pilot",
            role="squad_member",
            role_name="Squad Member",
            ship_type_id=587,
            ship_name="Rifter",
            solar_system_id=1,
            solar_system_name="Amamake",
            squad_id=1,
            wing_id=1,
        )
        soon = timezone.now() + timedelta(minutes=16)
        self.assertLess(state(self.main, "killmails").next_due_at, soon)
        self.assertLess(state(self.main, "mining").next_due_at, soon)
        self.assertGreater(state(self.main, "skills").next_due_at, soon)

    @patch("groups.signals.sync_user_community_groups")
    def test_back_from_leave_makes_everything_due(self, _):
        status = UserCommunityStatus.objects.create(
            user=self.user, status=UserCommunityStatus.STATUS_ON_LEAVE
        )
        self.assertGreater(
            state(self.alt, "skills").next_due_at, timezone.now()
        )
        status.status = UserCommunityStatus.STATUS_ACTIVE
        status.save()
        self.assertLessEqual(
            state(self.alt, "skills").next_due_at, timezone.now()
        )


class ReportingTests(SyncTestCase):
    def test_freshness_report_and_commands(self):
        sync.run_character_sync(self.main)
        EveCharacterSyncState.objects.filter(
            character=self.main, section="assets"
        ).update(synced_at=timezone.now() - timedelta(hours=9))
        report = sync.freshness_report()
        assets = report["sections"]["assets"]
        self.assertEqual(assets.in_scope, 1)
        self.assertEqual(assets.overdue, 1)
        out = StringIO()
        call_command("character_sync_status", stdout=out)
        self.assertIn("assets", out.getvalue())

    def test_spread_creates_rows_within_each_interval(self):
        out = StringIO()
        call_command("spread_character_sync", stdout=out)
        rows = EveCharacterSyncState.objects.filter(character=self.main)
        self.assertEqual(rows.count(), len(sync.SECTIONS))
        horizon = timezone.now() + timedelta(days=7, minutes=1)
        self.assertTrue(all(row.next_due_at <= horizon for row in rows))
        self.assertFalse(
            EveCharacterSyncState.objects.filter(
                character=self.outsider
            ).exists()
        )

    @override_settings(CHARACTER_SYNC_MODE="scheduled")
    def test_health_warns_when_behind(self):
        sync.run_character_sync(self.main)
        EveCharacterSyncState.objects.filter(
            character=self.main, section="assets"
        ).update(synced_at=timezone.now() - timedelta(hours=9))
        with self.assertLogs(
            "eveonline.tasks.character_sync", "WARNING"
        ) as logs:
            tasks.report_character_sync_health()
        self.assertTrue(any("assets behind" in line for line in logs.output))


class BudgetReportingTests(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def test_observed_django_esi_errors_count_once(self):
        before = esi_budget.error_budget()
        response = _observed(EsiResponse(response_code=404), {})
        self.assertEqual(esi_budget.error_budget(), before - 1)
        esi_budget.note_response("char-killmail", 1, response)
        self.assertEqual(esi_budget.error_budget(), before - 1)

    def test_error_limit_pauses_every_group(self):
        _observed(
            EsiResponse(response_code=420), {"X-Esi-Error-Limit-Reset": 40}
        )
        self.assertGreater(esi_budget.pause_remaining(None), 0)


class ServiceCorporationContractTests(TestCase):
    @patch(
        "eveonline.tasks.corporations.get_esi_downtime_countdown",
        return_value=0,
    )
    @patch(
        "eveonline.tasks.corporations.refresh_corporation_contracts",
        return_value=4,
    )
    def test_freight_contracts(self, refresh, _):

        self.assertEqual(sync_freight_contracts(), 4)
        refresh.assert_called_once_with(FREIGHT_CORPORATION_ID)

    @patch("eveonline.utils.get_esi_downtime_countdown", return_value=0)
    @patch("buyback.tasks.refresh_buyback_ledger", return_value={})
    @patch(
        "eveonline.helpers.corporations.update_corporation_contracts",
        return_value=2,
    )
    def test_buyback_contracts_skip_hangar_and_sells(self, refresh, ledger, _):

        result = sync_buyback_contracts_task()
        refresh.assert_called_once_with(BUYBACK_CORPORATION_ID)
        kwargs = ledger.call_args.kwargs
        self.assertTrue(kwargs["sync_contracts"])
        self.assertFalse(kwargs["snapshot_hangar"])
        self.assertFalse(kwargs["sync_sell_orders"])
        self.assertEqual(result["corporation_contracts"], 2)
