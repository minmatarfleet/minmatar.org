from __future__ import annotations

import importlib
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.apps import apps as django_apps
from django.core.management import call_command

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from feed.helpers.fleet_kills import fleet_kill_report, match_fleet_killmails
from feed.models import FeedEvent, FeedEventFleetLink, FeedKillmail
from feed.rollups import fleet_kills as fleet_kills_rollup
from feed.rollups.fleet_kills import (
    SETTLE_AFTER,
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
        cache.clear()
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

    def add_member(self, character_id, joined, last_seen, first_seen=None):
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
            join_time=joined,
            created_at=first_seen or joined,
            updated_at=last_seen,
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

    def window(self):
        return RollupContext(
            since=timezone.now() - timedelta(hours=48), until=timezone.now()
        )

    def test_rejoin_keeps_credit_from_first_sighting(self):
        """ESI moves join_time forward on a rejoin; created_at does not."""
        rejoiner = 2003
        self.add_member(
            rejoiner,
            self.at(50),
            self.at(60),
            first_seen=self.at(5),
        )
        make_killmail(1, self.at(10), victim=ENEMY, attackers=[rejoiner])

        summary = match_fleet_killmails(self.instance)

        self.assertEqual([1], [k.killmail_id for k in summary.killmails])

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

    def test_report_caches_the_live_match(self):
        make_killmail(1, self.at(10), victim=ENEMY, attackers=[PILOT])
        fleet_kill_report(self.fleet)

        with patch("feed.helpers.fleet_kills.match_fleet_killmails") as match:
            report = fleet_kill_report(self.fleet)

        match.assert_not_called()
        self.assertEqual(1, report["ships_destroyed"])

    def test_format_isk(self):
        self.assertEqual("2.2B", format_isk(2_197_437_282))
        self.assertEqual("464.3M", format_isk(464_302_706))
        self.assertEqual("950K", format_isk(950_000))

    def test_settled_card_is_left_alone(self):
        make_killmail(1, self.at(10), victim=ENEMY, attackers=[PILOT])
        write_rollup_results(run_fleet_kills_rollup(self.window()))
        FeedEvent.objects.update(
            computed_at=self.instance.end_time + SETTLE_AFTER
        )

        self.assertEqual([], run_fleet_kills_rollup(self.window()))

    def test_unsettled_card_picks_up_a_late_killmail(self):
        make_killmail(1, self.at(10), victim=ENEMY, attackers=[PILOT])
        write_rollup_results(run_fleet_kills_rollup(self.window()))
        make_killmail(2, self.at(20), victim=ENEMY, attackers=[PILOT])

        write_rollup_results(run_fleet_kills_rollup(self.window()))

        event = FeedEvent.objects.get(rollup_code="fleet_kills")
        self.assertEqual(2, event.payload["ships_destroyed"])
        self.assertEqual(2, event.killmail_links.count())

    def test_open_fleet_goes_quiet_when_the_poller_stops(self):
        EveFleetInstance.objects.filter(pk=self.instance.pk).update(
            end_time=None, last_updated=timezone.now()
        )
        make_killmail(1, self.at(10), victim=ENEMY, attackers=[PILOT])
        self.assertTrue(run_fleet_kills_rollup(self.window())[0].is_active)

        EveFleetInstance.objects.filter(pk=self.instance.pk).update(
            last_updated=timezone.now() - timedelta(hours=1)
        )

        self.assertFalse(run_fleet_kills_rollup(self.window())[0].is_active)

    def test_standing_fleets_are_left_to_campaigns(self):
        EveFleet.objects.filter(pk=self.fleet.pk).update(type="standing")
        make_killmail(1, self.at(10), victim=ENEMY, attackers=[PILOT])

        self.assertEqual([], run_fleet_kills_rollup(self.window()))

    def test_one_failing_fleet_does_not_sink_the_pass(self):
        make_killmail(1, self.at(10), victim=ENEMY, attackers=[PILOT])
        with patch.object(
            fleet_kills_rollup,
            "build_fleet_kills_result",
            side_effect=RuntimeError("boom"),
        ):
            self.assertEqual([], run_fleet_kills_rollup(self.window()))

    def test_names_are_reused_and_esi_failure_is_tolerated(self):
        make_killmail(1, self.at(10), victim=ENEMY, attackers=[PILOT])
        with patch(
            "feed.helpers.fleet_kills.resolve_character_names",
            return_value={ENEMY: "Puwpuw"},
        ):
            write_rollup_results(run_fleet_kills_rollup(self.window()))

        with patch(
            "feed.helpers.fleet_kills.resolve_character_names",
            side_effect=RuntimeError("ESI down"),
        ):
            results = run_fleet_kills_rollup(self.window())

        row = results[0].payload["killmails"][0]
        self.assertEqual("Puwpuw", row["victim_character_name"])

    def test_wipe_rebuild_keeps_fleet_cards(self):
        make_killmail(1, self.at(10), victim=ENEMY, attackers=[PILOT])
        write_rollup_results(run_fleet_kills_rollup(self.window()))

        call_command("rebuild_feed_rollups", "--wipe", stdout=StringIO())

        self.assertTrue(
            FeedEvent.objects.filter(rollup_code="fleet_kills").exists()
        )

    def test_losses_only_title(self):
        make_killmail(
            1, self.at(50), victim=LATE_PILOT, attackers=[ENEMY], ship=RIFTER
        )

        result = build_fleet_kills_result(self.instance)

        self.assertEqual(
            f"Fleet {self.fleet.id}: lost 1 ship, 1.0B ISK", result.title
        )


BACKFILL = importlib.import_module(
    "feed.migrations.0018_backfill_fleet_2393_kills"
)


@patch(
    "feed.helpers.fleet_kills.resolve_character_names",
    lambda ids: {},
)
class Fleet2393BackfillTestCase(TestCase):
    """The data migration, run against a stand-in for fleet 2393."""

    def setUp(self):
        disconnect_fleet_signals()
        self.start = timezone.now() - timedelta(days=5)

    def make_fleet(self, username):
        user = User.objects.create(username=username)
        fleet = EveFleet.objects.create(
            id=BACKFILL.FLEET_ID,
            start_time=self.start,
            type="non_strategic",
            status="complete",
            created_by=user,
        )
        instance = EveFleetInstance.objects.create(
            id=1260612315062, eve_fleet=fleet
        )
        EveFleetInstance.objects.filter(pk=instance.pk).update(
            start_time=self.start, end_time=self.start + timedelta(hours=3)
        )
        member = EveFleetInstanceMember.objects.create(
            eve_fleet_instance=instance,
            character_id=PILOT,
            character_name="Pilot",
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
            join_time=self.start,
            created_at=self.start,
            updated_at=self.start + timedelta(hours=3),
        )
        make_killmail(
            139189498,
            self.start + timedelta(hours=1),
            victim=ENEMY,
            attackers=[PILOT],
        )
        return instance

    def test_backfills_a_fleet_outside_the_rollup_window(self):
        instance = self.make_fleet(BACKFILL.FC_USERNAME)

        BACKFILL.backfill(django_apps, None)

        event = FeedEvent.objects.get(rollup_code="fleet_kills")
        self.assertEqual(f"fleet_kills:{instance.id}", event.cluster_key)
        self.assertEqual("Fleet 2393: 1 ship destroyed, 1.0B ISK", event.title)
        self.assertTrue(
            FeedEventFleetLink.objects.filter(
                feed_event=event, fleet_instance_id=instance.id
            ).exists()
        )

    def test_skips_a_fleet_2393_that_is_not_bearthatcares(self):
        self.make_fleet("someone_else")

        BACKFILL.backfill(django_apps, None)

        self.assertFalse(FeedEvent.objects.exists())

    def test_a_failure_does_not_raise(self):
        self.make_fleet(BACKFILL.FC_USERNAME)
        with patch(
            "feed.rollups.writer.write_rollup_results",
            side_effect=RuntimeError("boom"),
        ):
            BACKFILL.backfill(django_apps, None)

        self.assertFalse(FeedEvent.objects.exists())
