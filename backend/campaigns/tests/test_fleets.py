"""Fleet attendance, which ESI only half tells us about."""

from datetime import timedelta

import factory
from django.db.models import signals
from django.test import TestCase
from django.utils import timezone

from campaigns.helpers import campaign_day, day_bounds
from campaigns.models import CampaignKillmail
from campaigns.services import fleets
from campaigns.services.attribution import attribute_feed_killmail
from campaigns.tests.helpers import (
    KAMELA,
    enlist,
    make_campaign,
    make_feed_killmail,
)
from fleets.models import EveFleet, EveFleetInstance, EveFleetInstanceMember


class FleetAttendanceTests(TestCase):
    def setUp(self):
        self.campaign = make_campaign()
        self.user, self.character = enlist(self.campaign, "pilot", 6001)
        self.today = campaign_day()
        self.start, self.end = day_bounds(self.today)

    def _fleet(self, fleet_type="standing", created_by=None):
        with factory.django.mute_signals(signals.pre_save, signals.post_save):
            return EveFleet.objects.create(
                type=fleet_type,
                start_time=self.start,
                campaign=self.campaign,
                created_by=created_by,
            )

    def _instance(self, fleet, start=None, end=None, last_updated=None):
        instance = EveFleetInstance.objects.create(
            id=fleet.id * 1000, eve_fleet=fleet, end_time=end
        )
        # start_time is auto_now_add, so it has to be set after the fact.
        EveFleetInstance.objects.filter(pk=instance.pk).update(
            start_time=start or self.start,
            last_updated=last_updated or (self.start + timedelta(hours=2)),
        )
        instance.refresh_from_db()
        return instance

    def _member(self, instance, character_id, join_time, system=KAMELA):
        member = EveFleetInstanceMember.objects.create(
            eve_fleet_instance=instance,
            character_id=character_id,
            character_name="Pilot",
            role="squad_member",
            role_name="Squad Member",
            ship_type_id=621,
            ship_name="Rifter",
            solar_system_id=system,
            solar_system_name="Kamela",
            squad_id=1,
            wing_id=1,
        )
        EveFleetInstanceMember.objects.filter(pk=member.pk).update(
            join_time=join_time
        )
        member.refresh_from_db()
        return member

    def test_a_pilot_in_a_campaign_fleet_is_counted(self):
        fleet = self._fleet()
        instance = self._instance(fleet)
        self._member(instance, 6001, self.start + timedelta(minutes=10))

        rows = fleets.attendance_for_day(self.campaign, self.today)
        self.assertEqual(rows[self.user.id]["attended"], 1)
        self.assertTrue(rows[self.user.id]["standing_day"])

    def test_a_fleet_with_no_campaign_does_not_count(self):
        with factory.django.mute_signals(signals.pre_save, signals.post_save):
            fleet = EveFleet.objects.create(
                type="strategic", start_time=self.start
            )
        instance = self._instance(fleet)
        self._member(instance, 6001, self.start + timedelta(minutes=10))

        self.assertEqual(
            fleets.attendance_for_day(self.campaign, self.today), {}
        )

    def test_a_pilot_who_joined_yesterday_still_counts_today(self):
        """ESI reports when someone joined, never when they left.

        A standing fleet is always up, so filtering on the join time would
        credit a pilot for exactly one day and nothing after it.
        """
        yesterday = self.today - timedelta(days=1)
        fleet = self._fleet()
        instance = self._instance(
            fleet,
            start=self.start - timedelta(days=1),
            last_updated=self.start + timedelta(hours=3),
        )
        self._member(instance, 6001, self.start - timedelta(hours=20))

        for day in (yesterday, self.today):
            rows = fleets.attendance_for_day(self.campaign, day)
            self.assertEqual(rows[self.user.id]["attended"], 1, day)

    def test_minutes_stop_when_the_poller_stopped_looking(self):
        """An untracked fleet must not accrue time for the rest of the day."""
        fleet = self._fleet()
        instance = self._instance(
            fleet, last_updated=self.start + timedelta(minutes=45)
        )
        self._member(instance, 6001, self.start)

        rows = fleets.attendance_for_day(self.campaign, self.today)
        self.assertEqual(rows[self.user.id]["standing_minutes"], 45)

    def test_a_fleet_in_a_primary_system_is_recognised(self):
        fleet = self._fleet()
        instance = self._instance(fleet)
        self._member(instance, 6001, self.start, system=KAMELA)

        rows = fleets.attendance_for_day(self.campaign, self.today)
        self.assertEqual(rows[self.user.id]["attended_primary"], 1)

    def test_a_fleet_that_never_reached_a_campaign_system_is_not_primary(self):
        fleet = self._fleet()
        instance = self._instance(fleet)
        self._member(instance, 6001, self.start, system=30002537)

        rows = fleets.attendance_for_day(self.campaign, self.today)
        self.assertEqual(rows[self.user.id]["attended_primary"], 0)

    def test_leading_a_gang_is_credited_to_the_creator(self):
        fleet = self._fleet(fleet_type="gang", created_by=self.user)
        self._instance(fleet)

        rows = fleets.attendance_for_day(self.campaign, self.today)
        self.assertEqual(rows[self.user.id]["gangs_led"], 1)
        self.assertEqual(rows[self.user.id]["led"], 0)


class FleetKillmailLinkTests(TestCase):
    def setUp(self):
        self.campaign = make_campaign()
        self.user, _ = enlist(self.campaign, "pilot", 6101)
        self.today = campaign_day()
        self.start, _ = day_bounds(self.today)

    def test_a_kill_during_a_campaign_fleet_is_linked_to_it(self):
        with factory.django.mute_signals(signals.pre_save, signals.post_save):
            fleet = EveFleet.objects.create(
                type="standing",
                start_time=self.start,
                campaign=self.campaign,
            )
        instance = EveFleetInstance.objects.create(id=99001, eve_fleet=fleet)
        EveFleetInstance.objects.filter(pk=instance.pk).update(
            start_time=self.start
        )
        EveFleetInstanceMember.objects.create(
            eve_fleet_instance=instance,
            character_id=6101,
            character_name="Pilot",
            role="squad_member",
            role_name="Squad Member",
            ship_type_id=621,
            ship_name="Rifter",
            solar_system_id=KAMELA,
            solar_system_name="Kamela",
            squad_id=1,
            wing_id=1,
        )

        feed_killmail = make_feed_killmail(
            701,
            victim_character_id=9999,
            attacker_ids=[6101],
            killmail_time=self.start + timedelta(hours=1),
        )
        attribute_feed_killmail(feed_killmail)

        linked = fleets.link_killmails_to_fleets(self.campaign, self.today)
        self.assertEqual(linked, 1)

        mail = CampaignKillmail.objects.get(killmail_id=701)
        self.assertEqual(mail.fleet_id, fleet.id)

    def test_a_kill_with_no_fleet_up_is_left_alone(self):
        feed_killmail = make_feed_killmail(
            702,
            victim_character_id=9999,
            attacker_ids=[6101],
            killmail_time=timezone.now(),
        )
        attribute_feed_killmail(feed_killmail)

        self.assertEqual(
            fleets.link_killmails_to_fleets(self.campaign, self.today), 0
        )
        self.assertIsNone(
            CampaignKillmail.objects.get(killmail_id=702).fleet_id
        )
