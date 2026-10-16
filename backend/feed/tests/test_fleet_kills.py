from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from feed.helpers.fleet_kills import fleet_kill_report, match_fleet_killmails
from feed.models import FeedEvent, FeedEventFleetLink, FeedKillmail
from feed.rollups.fleet_kills import (
    build_fleet_kills_result,
    format_isk,
    run_fleet_kills_rollup,
)
from feed.rollups.types import RollupContext
from feed.rollups.writer import write_rollup_results
from fleets.models import EveFleet, EveFleetInstance, EveFleetInstanceMember
from fleets.tests import disconnect_fleet_signals

PILOT = 2001
LATE_PILOT = 2002
ENEMY = 3001
VARGUR = 28665
RIFTER = 587
CAPSULE = 670


def make_killmail(
    killmail_id, moment, *, victim, attackers, ship=VARGUR, value=10**9
):
    return FeedKillmail.objects.create(
        killmail_id=killmail_id,
        hash=f"h{killmail_id}",
        killmail_time=moment,
        solar_system_id=30002097,
        victim_character_id=victim,
        victim_ship_type_id=ship,
        attacker_summary=[{"character_id": a} for a in attackers],
        raw_killmail={},
        zkb_meta={"totalValue": value},
    )


@patch(
    "feed.helpers.fleet_kills.resolve_character_names",
    lambda ids: {},
)
class FleetKillsTestCase(TestCase):
    def setUp(self):
        disconnect_fleet_signals()
        self.start = timezone.now() - timedelta(hours=2)
        self.fc = User.objects.create(username="fc")
        self.fleet = EveFleet.objects.create(
            start_time=self.start,
            type="non_strategic",
            status="complete",
            created_by=self.fc,
        )
        self.instance = EveFleetInstance.objects.create(
            id=1260612315062, eve_fleet=self.fleet
        )
        EveFleetInstance.objects.filter(pk=self.instance.pk).update(
            start_time=self.start, end_time=self.start + timedelta(hours=1)
        )
        self.instance.refresh_from_db()
        # In fleet for the first hour.
        self.add_member(PILOT, self.start, self.start + timedelta(hours=1))
        # Joined 40 minutes in.
        self.add_member(
            LATE_PILOT,
            self.start + timedelta(minutes=40),
            self.start + timedelta(hours=1),
        )

    def add_member(self, character_id, joined, last_seen):
        member = EveFleetInstanceMember.objects.create(
            eve_fleet_instance=self.instance,
            character_id=character_id,
            character_name=f"Pilot {character_id}",
            role="squad_member",
            role_name="Squad Member",
            ship_type_id=RIFTER,
            ship_name="Rifter",
            solar_system_id=30002097,
            solar_system_name="Klogori",
            squad_id=1,
            wing_id=1,
        )
        EveFleetInstanceMember.objects.filter(pk=member.pk).update(
            join_time=joined, updated_at=last_seen
        )

    def at(self, minutes):
        return self.start + timedelta(minutes=minutes)

    def test_kill_needs_a_pilot_in_fleet_at_the_time(self):
        make_killmail(1, self.at(10), victim=ENEMY, attackers=[PILOT])
        # LATE_PILOT had not joined yet.
        make_killmail(2, self.at(20), victim=ENEMY, attackers=[LATE_PILOT])
        # PILOT had left the fleet by then.
        make_killmail(3, self.at(90), victim=ENEMY, attackers=[PILOT])

        summary = match_fleet_killmails(self.instance)

        self.assertEqual([1], [k.killmail_id for k in summary.killmails])
        self.assertEqual("kill", summary.killmails[0].outcome)

    def test_victim_in_fleet_is_a_loss(self):
        make_killmail(
            1, self.at(50), victim=LATE_PILOT, attackers=[ENEMY], ship=RIFTER
        )

        summary = match_fleet_killmails(self.instance)

        self.assertEqual(["loss"], [k.outcome for k in summary.killmails])

    def test_counts_pilots_on_the_mail(self):
        make_killmail(
            1, self.at(45), victim=ENEMY, attackers=[PILOT, LATE_PILOT, 9]
        )

        summary = match_fleet_killmails(self.instance)

        self.assertEqual(2, summary.killmails[0].fleet_pilots)

    def test_capsules_count_towards_isk_not_ships(self):
        make_killmail(1, self.at(10), victim=ENEMY, attackers=[PILOT])
        make_killmail(
            2,
            self.at(11),
            victim=ENEMY,
            attackers=[PILOT],
            ship=CAPSULE,
            value=30 * 10**6,
        )

        result = build_fleet_kills_result(self.instance)

        self.assertEqual(1, result.payload["ships_destroyed"])
        self.assertEqual(1, result.payload["pods_destroyed"])
        self.assertEqual(10**9 + 30 * 10**6, result.payload["isk_destroyed"])
        self.assertEqual([1], result.payload["headline"])

    def test_no_killmails_no_card(self):
        self.assertIsNone(build_fleet_kills_result(self.instance))

    def test_rollup_writes_one_linked_card_per_instance(self):
        make_killmail(1, self.at(10), victim=ENEMY, attackers=[PILOT])
        make_killmail(
            2, self.at(50), victim=LATE_PILOT, attackers=[ENEMY], ship=RIFTER
        )
        ctx = RollupContext(
            since=timezone.now() - timedelta(hours=48), until=timezone.now()
        )

        write_rollup_results(run_fleet_kills_rollup(ctx))
        write_rollup_results(run_fleet_kills_rollup(ctx))

        event = FeedEvent.objects.get(rollup_code="fleet_kills")
        self.assertEqual(FeedEvent.Kind.FLEET_KILLS, event.kind)
        self.assertEqual(f"fleet_kills:{self.instance.id}", event.cluster_key)
        self.assertFalse(event.is_active)
        self.assertEqual(
            f"Fleet {self.fleet.id}: 1 ship destroyed, 1.0B ISK", event.title
        )
        self.assertEqual(2, event.killmail_links.count())
        self.assertEqual(
            [self.instance.id],
            list(
                FeedEventFleetLink.objects.filter(
                    feed_event=event
                ).values_list("fleet_instance_id", flat=True)
            ),
        )

    def test_rollup_skips_instances_outside_the_window(self):
        make_killmail(1, self.at(10), victim=ENEMY, attackers=[PILOT])
        ctx = RollupContext(
            since=timezone.now() - timedelta(minutes=30),
            until=timezone.now(),
        )

        self.assertEqual([], run_fleet_kills_rollup(ctx))

    def test_report_reads_stored_card_after_killmails_are_purged(self):
        make_killmail(1, self.at(10), victim=ENEMY, attackers=[PILOT])
        write_rollup_results([build_fleet_kills_result(self.instance)])
        FeedKillmail.objects.all().delete()

        report = fleet_kill_report(self.fleet)

        self.assertEqual([1], [k["killmail_id"] for k in report["killmails"]])
        self.assertEqual(10**9, report["isk_destroyed"])

    def test_report_matches_live_while_the_fleet_is_open(self):
        EveFleetInstance.objects.filter(pk=self.instance.pk).update(
            end_time=None
        )
        make_killmail(1, self.at(10), victim=ENEMY, attackers=[PILOT])

        report = fleet_kill_report(self.fleet)

        self.assertTrue(report["tracked"])
        self.assertEqual(1, report["ships_destroyed"])

    def test_format_isk(self):
        self.assertEqual("2.2B", format_isk(2_197_437_282))
        self.assertEqual("464.3M", format_isk(464_302_706))
        self.assertEqual("950K", format_isk(950_000))
