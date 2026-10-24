"""The fleet report the FC gets once the fight timeline settles."""

from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch
from urllib.parse import urlencode

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from app.test import TestCase
from feed.helpers.fleet_pilots import invalidate_fleet_pilot_cache
from fleets.helpers.close_mail import format_duration, format_eve_window
from fleets.models import EveFleet, EveFleetInstance
from fleets.tasks import settle_fight_timeline
from fleets.test_fight_timeline import killmail, member
from fleets.tests import disconnect_fleet_signals
from notifications.types.fleets import render_fleet_closed

UTC = dt_timezone.utc


@override_settings(
    WEB_LINK_URL="https://my.minmatar.org",
    DISCORD_GUILD_ID=1041384161505722368,
    DISCORD_AARS_FORUM_CHANNEL_ID=1069380111897481256,
)
@patch("fleets.helpers.fights.collect.resolve_entity_names", lambda ids: {})
@patch("feed.helpers.fleet_kills.resolve_character_names", lambda ids: {})
@patch("fleets.helpers.fights.timeline.lookup_evekill_battles", lambda t: {})
@patch("fleets.helpers.close_mail.notify_user")
class FleetReportMailTestCase(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        invalidate_fleet_pilot_cache()
        disconnect_fleet_signals()
        self.end = timezone.now() - timedelta(hours=2, minutes=5)
        self.start = self.end - timedelta(minutes=50)
        self.fleet = EveFleet.objects.create(
            start_time=self.start,
            type="non_strategic",
            status="complete",
            objective="Roam Hevrice",
            created_by=self.user,
        )
        self.instance = EveFleetInstance.objects.create(
            id=1183712315753, eve_fleet=self.fleet
        )
        EveFleetInstance.objects.filter(pk=self.instance.pk).update(
            start_time=self.start, end_time=self.end, last_updated=self.end
        )

    def at(self, minutes):
        return self.start + timedelta(minutes=minutes)

    def iso(self, minutes):
        return self.at(minutes).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    def fly(self):
        """Three pilots, a win and then a loss 20 minutes later."""
        for pilot in (2001, 2002, 2003):
            member(self.instance, pilot, self.start, self.end)
        for index in range(5):
            killmail(
                100 + index,
                self.at(10 + index),
                victim=4000 + index,
                attackers=[2001, 2002, 5000 + index],
            )
        for index in range(4):
            killmail(
                200 + index,
                self.at(35 + index),
                victim=2001 + index % 3,
                attackers=[6000, 6001],
            )

    def test_settling_mails_the_fc_the_numbers_and_round_reports(self, notify):
        self.fly()

        settle_fight_timeline(self.fleet.id)

        notify.assert_called_once()
        args, kwargs = notify.call_args
        self.assertEqual(self.user, args[0])
        self.assertEqual("fleets.closed", args[1])
        self.assertEqual(
            f"fleets.closed:{self.fleet.id}:report", kwargs["idempotency_key"]
        )
        context = args[2]
        self.assertEqual(3, context["our_pilots"])
        self.assertEqual(5, context["totals"]["ships_destroyed"])
        self.assertEqual(4, context["totals"]["ships_lost"])
        self.assertEqual(56, context["totals"]["efficiency"])
        self.assertEqual(2, context["round_count"])
        report_url = (
            f"https://my.minmatar.org/fleets/history/{self.fleet.id}/report"
        )
        self.assertEqual(report_url, context["battle_report_url"])
        # A minute either side of each round, as the Fights tab links it.
        self.assertEqual(
            [
                f"{report_url}?{urlencode({'start': self.iso(9), 'end': self.iso(15)})}",
                f"{report_url}?{urlencode({'start': self.iso(34), 'end': self.iso(39)})}",
            ],
            [report["url"] for report in context["battle_reports"]],
        )
        self.assertEqual(
            f"https://my.minmatar.org/fleets/history/{self.fleet.id}",
            context["fleet_url"],
        )
        self.assertEqual(
            f"https://my.minmatar.org/fleets/{self.fleet.id}/kills",
            context["kill_report_url"],
        )
        self.assertTrue(context["kill_report_public"])
        self.assertIn(
            "zkillboard.com/related/", context["links"]["zkillboard"]
        )
        self.assertEqual("50m", context["duration"])

        body = render_fleet_closed(context)["eve_mail_body"]
        self.assertIn("Roam Hevrice", body)
        self.assertIn("Pilots: 3 ours vs 7 hostiles", body)
        self.assertIn("Killed: 5 ships · 500.0M ISK", body)
        self.assertIn("Lost: 4 ships · 400.0M ISK", body)
        self.assertIn("Fights: 2 rounds, 0 skirmishes", body)
        self.assertIn(
            f'<a href="{report_url}">Battle report</a> · the whole fleet',
            body,
        )
        self.assertIn(">Round 2</a> · ", body)

    def test_members_only_group_fleet_links_the_kills_tab(self, notify):
        self.fly()
        EveFleet.objects.filter(pk=self.fleet.pk).update(
            host_group_id=self.make_group().id, open_to_alliance=False
        )

        settle_fight_timeline(self.fleet.id)

        context = notify.call_args.args[2]
        self.assertEqual(
            f"https://my.minmatar.org/fleets/history/{self.fleet.id}#kills",
            context["kill_report_url"],
        )
        self.assertFalse(context["kill_report_public"])

    def test_fleet_still_open_is_not_mailed(self, notify):
        self.fly()
        EveFleet.objects.filter(pk=self.fleet.pk).update(status="active")

        settle_fight_timeline(self.fleet.id)

        notify.assert_not_called()

    def test_fleet_that_tracked_nobody_is_not_mailed(self, notify):
        settle_fight_timeline(self.fleet.id)

        notify.assert_not_called()

    def make_group(self):
        # pylint: disable=import-outside-toplevel
        from tribes.models import Tribe, TribeGroup

        tribe = Tribe.objects.create(name="Capitals", slug="capitals")
        return TribeGroup.objects.create(tribe=tribe, name="Dreads")


@override_settings(WEB_LINK_URL="https://my.minmatar.org")
class FleetReportCopyTestCase(SimpleTestCase):
    def context(self, **overrides):
        return {
            "fleet_id": 1234,
            "fleet_type": "Non Strategic Operation",
            "location_name": "Amamake",
            "objective": "Roam Hevrice <3",
            "doctrine_name": "Hurricanes",
            "time_window": "2026-08-30 15:01–19:01 EVE",
            "duration": "4h 00m",
            "our_pilots": 42,
            "hostile_pilots": 57,
            "totals": {
                "ships_destroyed": 18,
                "pods_destroyed": 7,
                "ships_lost": 4,
                "pods_lost": 1,
                "isk_destroyed": 2_400_000_000,
                "isk_lost": 310_000_000,
                "efficiency": 89,
            },
            "round_count": 2,
            "skirmish_count": 2,
            "battle_reports": [
                {
                    "kind": "round",
                    "number": 1,
                    "start": "15:42",
                    "minutes": 12,
                    "systems": ["Hevrice", "Ezzara"],
                    "ships_destroyed": 14,
                    "ships_lost": 1,
                    "efficiency": 92,
                    "url": (
                        "https://my.minmatar.org/fleets/history/1234/report"
                        "?start=a&end=b"
                    ),
                },
            ],
            "biggest_kill": {
                "ship_name": "Sleipnir",
                "victim_name": "Some Pilot",
                "isk": 610_000_000,
            },
            "biggest_loss": {
                "ship_name": "Hurricane",
                "victim_name": "",
                "isk": 80_000_000,
            },
            "hostile_groups": [
                {"name": "Snuffed Out", "pilots": 21},
                {"name": "Goonswarm Federation", "pilots": 0},
            ],
            "fleet_url": "https://my.minmatar.org/fleets/history/1234",
            "kill_report_url": "https://my.minmatar.org/fleets/1234/kills",
            "kill_report_public": True,
            "battle_report_url": (
                "https://my.minmatar.org/fleets/history/1234/report"
            ),
            "links": {
                "zkillboard": "https://zkillboard.com/related/1/202608301500/",
                "brtools": "https://br.evetools.org/related/1/202608301500",
                "evekill": None,
            },
            "aar_url": "https://discord.com/channels/1/2",
            **overrides,
        }

    def test_mail_has_numbers_and_named_report_links(self):
        payload = render_fleet_closed(self.context())
        body = payload["eve_mail_body"]

        self.assertEqual(
            "Fleet 1234 report — 18 killed, 4 lost, 89%", payload["subject"]
        )
        self.assertNotIn("\n", body)
        for line in (
            "<b>Fleet 1234 · Roam Hevrice &lt;3</b>",
            "Non Strategic Operation · Amamake · Hurricanes",
            "2026-08-30 15:01–19:01 EVE · 4h 00m",
            "Killed: 18 ships, 7 pods · 2.4B ISK",
            "Lost: 4 ships, 1 pod · 310.0M ISK",
            "Efficiency: 89%",
            "Pilots: 42 ours vs 57 hostiles",
            "Fights: 2 rounds, 2 skirmishes",
            "Fought: Snuffed Out (21 pilots), Goonswarm Federation",
            "Biggest kill: Sleipnir (Some Pilot) · 610.0M ISK",
            "Biggest loss: Hurricane · 80.0M ISK",
            '<a href="https://my.minmatar.org/fleets/1234/kills">'
            "Kill report</a> · every kill and loss, open to anyone",
            '<a href="https://my.minmatar.org/fleets/history/1234/report">'
            "Battle report</a> · the whole fleet, every side<br>"
            '› <a href="https://my.minmatar.org/fleets/history/1234/report'
            '?start=a&end=b">Round 1</a> · 15:42 EVE · Hevrice, Ezzara · '
            "14 killed, 1 lost · 92%",
            'Also: <a href="https://my.minmatar.org/fleets/history/1234#aar">'
            'Fights tab</a> · <a href="https://zkillboard.com/related/1/'
            '202608301500/">zKillboard</a> · <a href="https://br.evetools'
            '.org/related/1/202608301500">br.evetools</a>',
            'Write it up in <a href="https://discord.com/channels/1/2">'
            "#aars</a>, then add the link on the",
            "o7<br>BearThatCares",
        ):
            self.assertIn(line, body)
        self.assertNotIn("eve-kill", body)
        self.assertEqual(
            "https://my.minmatar.org/fleets/history/1234", payload["url"]
        )

    def test_plain_text_spells_out_the_links(self):
        text = render_fleet_closed(self.context())["discord_message"]

        self.assertIn(
            "Kill report (https://my.minmatar.org/fleets/1234/kills)", text
        )
        self.assertIn("Fleet 1234 · Roam Hevrice <3\n", text)
        self.assertNotIn("<b>", text)

    def test_private_fleet_kill_report_is_for_members(self):
        body = render_fleet_closed(
            self.context(
                kill_report_url=(
                    "https://my.minmatar.org/fleets/history/1234#kills"
                ),
                kill_report_public=False,
            )
        )["eve_mail_body"]

        self.assertIn("Kill report</a> · every kill and loss, members", body)

    def test_quiet_fleet_skips_the_numbers(self):
        payload = render_fleet_closed(
            self.context(
                hostile_pilots=0,
                totals={},
                round_count=0,
                skirmish_count=0,
                battle_reports=[],
                biggest_kill=None,
                biggest_loss=None,
                hostile_groups=[],
                kill_report_url="",
                kill_report_public=False,
                battle_report_url="",
                links={},
            )
        )
        body = payload["eve_mail_body"]

        self.assertEqual("Fleet 1234 report", payload["subject"])
        self.assertIn("Pilots: 42 ours<br>No kills or losses on record.", body)
        self.assertNotIn("Battle report", body)
        self.assertNotIn("Kill report", body)
        self.assertIn("Also: <a", body)

    def test_skirmish_only_fleet_links_skirmish_reports(self):
        report = {
            **self.context()["battle_reports"][0],
            "kind": "skirmish",
            "number": None,
        }
        body = render_fleet_closed(self.context(battle_reports=[report]))[
            "eve_mail_body"
        ]

        self.assertIn(">Skirmish</a>", body)

    def test_long_nights_list_five_battle_reports(self):
        reports = [
            {**self.context()["battle_reports"][0], "number": number}
            for number in range(1, 8)
        ]
        body = render_fleet_closed(self.context(battle_reports=reports))[
            "eve_mail_body"
        ]

        self.assertIn(">Round 5</a>", body)
        self.assertNotIn(">Round 6</a>", body)
        self.assertIn("2 more on the <a", body)


class FleetReportFormatTests(SimpleTestCase):
    def test_window_and_duration(self):
        start = datetime(2026, 8, 30, 23, 1, tzinfo=UTC)
        end = datetime(2026, 8, 31, 1, 15, tzinfo=UTC)
        self.assertEqual(
            "2026-08-30 23:01 – 2026-08-31 01:15 EVE",
            format_eve_window(start, end),
        )
        self.assertEqual(
            "2026-08-30 23:01–23:40 EVE",
            format_eve_window(start, start + timedelta(minutes=39)),
        )
        self.assertEqual("2h 14m", format_duration(start, end))
        self.assertEqual(
            "39m", format_duration(start, start + timedelta(minutes=39))
        )
