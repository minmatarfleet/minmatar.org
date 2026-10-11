from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import MagicMock, patch

from django.test import override_settings
from django.utils import timezone

from app.test import TestCase
from fleets.helpers.roam_report import (
    create_roam_report,
    fleet_member_names,
    fleet_report_window,
    format_eve_window,
    isoformat_utc,
    parse_roam_report_url,
    publish_fleet_roam_report_impl,
)
from fleets.models import EveFleetInstance, EveFleetInstanceMember
from fleets.tests import (
    disconnect_fleet_signals,
    make_test_fleet,
    setup_fleet_reference_data,
)
from notifications.types.fleets import render_fleet_closed
from users.helpers import add_user_permission


def _member(instance, character_id, name):
    return EveFleetInstanceMember.objects.create(
        eve_fleet_instance=instance,
        character_id=character_id,
        character_name=name,
        role="squad_member",
        role_name="Squad Member",
        ship_type_id=1,
        ship_name="Rifter",
        solar_system_id=1,
        solar_system_name="Amo",
        squad_id=1,
        wing_id=1,
    )


class RoamReportHelperTestCase(TestCase):
    def setUp(self):
        disconnect_fleet_signals()
        setup_fleet_reference_data()
        super().setUp()
        add_user_permission(self.user, "view_evefleet")

    def test_member_names_are_unique_and_include_leavers(self):
        fleet = make_test_fleet("Roam", self.user)
        instance = EveFleetInstance.objects.create(id=11, eve_fleet=fleet)
        _member(instance, 1, "Vex Drake")
        _member(instance, 2, "Pilot Two")
        _member(instance, 3, "Vex Drake")
        self.assertEqual(
            fleet_member_names(fleet),
            ["Pilot Two", "Vex Drake"],
        )

    def test_report_window_uses_scheduled_start_when_earlier(self):
        start = datetime(2026, 8, 30, 15, 1, 17, tzinfo=dt_timezone.utc)
        fleet = make_test_fleet("Roam", self.user, start=start)
        instance = EveFleetInstance.objects.create(id=12, eve_fleet=fleet)
        EveFleetInstance.objects.filter(pk=instance.pk).update(
            start_time=start + timedelta(hours=1),
            end_time=start + timedelta(hours=4),
        )
        window_start, window_end = fleet_report_window(fleet)
        self.assertEqual(
            isoformat_utc(window_start), "2026-08-30T15:01:17+00:00"
        )
        self.assertEqual(
            isoformat_utc(window_end), "2026-08-30T19:01:17+00:00"
        )

    def test_format_eve_window_same_day(self):
        start = datetime(2026, 8, 30, 15, 1, tzinfo=dt_timezone.utc)
        end = datetime(2026, 8, 30, 19, 1, tzinfo=dt_timezone.utc)
        self.assertEqual(
            format_eve_window(start, end),
            "2026-08-30 15:01–19:01 EVE",
        )

    @override_settings(ROAM_REPORT_API_KEY="secret-token")
    @patch("fleets.helpers.roam_report.requests.post")
    def test_create_roam_report_posts_names_and_window(self, post_mock):
        response = MagicMock()
        response.ok = True
        response.headers = {}
        response.json.return_value = {"id": "csel3qi23akg00dfkju0"}
        response.text = ""
        post_mock.return_value = response

        start = datetime(2026, 8, 30, 15, 1, 17, tzinfo=dt_timezone.utc)
        end = datetime(2026, 8, 30, 19, 1, 17, tzinfo=dt_timezone.utc)
        url = create_roam_report(
            start=start,
            end=end,
            members=["Vex Drake"],
        )
        self.assertEqual(
            url, "https://www.roamreport.com/f/csel3qi23akg00dfkju0"
        )
        post_mock.assert_called_once()
        kwargs = post_mock.call_args.kwargs
        self.assertEqual(
            kwargs["json"],
            {
                "start": "2026-08-30T15:01:17+00:00",
                "end": "2026-08-30T19:01:17+00:00",
                "members": ["Vex Drake"],
            },
        )
        self.assertEqual(
            kwargs["headers"]["Authorization"], "Bearer secret-token"
        )

    @override_settings(ROAM_REPORT_API_KEY="")
    @patch("fleets.helpers.roam_report.requests.post")
    def test_create_roam_report_skips_without_key(self, post_mock):
        self.assertIsNone(
            create_roam_report(
                start=timezone.now(),
                end=timezone.now(),
                members=["Vex Drake"],
            )
        )
        post_mock.assert_not_called()

    def test_parse_location_header(self):
        response = MagicMock()
        response.headers = {
            "Location": "https://www.roamreport.com/f/abc",
        }
        response.json.side_effect = ValueError("no json")
        response.text = ""
        self.assertEqual(
            parse_roam_report_url(response),
            "https://www.roamreport.com/f/abc",
        )

    @override_settings(ROAM_REPORT_API_KEY="secret-token")
    @patch("fleets.helpers.roam_report.notify_user")
    @patch("fleets.helpers.roam_report.create_roam_report")
    def test_publish_saves_url_and_notifies(self, create_mock, notify_mock):
        create_mock.return_value = "https://www.roamreport.com/f/abc"
        start = datetime(2026, 8, 30, 15, 1, 17, tzinfo=dt_timezone.utc)
        fleet = make_test_fleet("Roam", self.user, start=start)
        fleet.status = "complete"
        fleet.save()
        instance = EveFleetInstance.objects.create(id=13, eve_fleet=fleet)
        EveFleetInstance.objects.filter(pk=instance.pk).update(
            start_time=start,
            end_time=start + timedelta(hours=4),
        )
        _member(instance, 1, "Vex Drake")

        url = publish_fleet_roam_report_impl(fleet.id)
        fleet.refresh_from_db()
        self.assertEqual(url, "https://www.roamreport.com/f/abc")
        self.assertEqual(fleet.roam_report_url, url)
        notify_mock.assert_called_once()
        args, kwargs = notify_mock.call_args
        self.assertEqual(args[0], self.user)
        self.assertEqual(args[1], "fleets.closed")
        self.assertEqual(args[2]["roam_report_url"], url)
        self.assertEqual(
            kwargs["idempotency_key"], f"fleets.closed:{fleet.id}"
        )
        create_mock.assert_called_once()

    @override_settings(ROAM_REPORT_API_KEY="secret-token")
    @patch("fleets.helpers.roam_report.notify_user")
    @patch("fleets.helpers.roam_report.create_roam_report")
    def test_publish_does_not_repost_existing_url(
        self, create_mock, notify_mock
    ):
        start = datetime(2026, 8, 30, 15, 1, 17, tzinfo=dt_timezone.utc)
        fleet = make_test_fleet("Roam", self.user, start=start)
        fleet.status = "complete"
        fleet.roam_report_url = "https://www.roamreport.com/f/existing"
        fleet.save()
        instance = EveFleetInstance.objects.create(id=14, eve_fleet=fleet)
        EveFleetInstance.objects.filter(pk=instance.pk).update(
            start_time=start,
            end_time=start + timedelta(hours=1),
        )
        _member(instance, 1, "Vex Drake")

        url = publish_fleet_roam_report_impl(fleet.id)
        self.assertEqual(url, "https://www.roamreport.com/f/existing")
        create_mock.assert_not_called()
        notify_mock.assert_called_once()

    @override_settings(ROAM_REPORT_API_KEY="secret-token")
    @patch("fleets.helpers.roam_report.notify_user")
    @patch("fleets.helpers.roam_report.requests.post")
    def test_empty_roster_skips_post_and_mail(self, post_mock, notify_mock):
        """A fleet that tracked nobody has nothing to report and nobody to
        thank, so it neither POSTs nor mails the FC."""
        start = datetime(2026, 8, 30, 15, 1, 17, tzinfo=dt_timezone.utc)
        fleet = make_test_fleet("Roam", self.user, start=start)
        fleet.status = "complete"
        fleet.save()
        instance = EveFleetInstance.objects.create(id=16, eve_fleet=fleet)
        EveFleetInstance.objects.filter(pk=instance.pk).update(
            start_time=start,
            end_time=start + timedelta(hours=1),
        )

        self.assertIsNone(publish_fleet_roam_report_impl(fleet.id))
        fleet.refresh_from_db()
        self.assertIsNone(fleet.roam_report_url)
        post_mock.assert_not_called()
        notify_mock.assert_not_called()

    @patch("fleets.endpoints.helpers.schedule_roam_report")
    def test_cancelled_fleet_does_not_schedule_roam_report(
        self, schedule_mock
    ):
        self.make_superuser()
        fleet = make_test_fleet("Roam", self.user)
        EveFleetInstance.objects.create(id=15, eve_fleet=fleet)
        response = self.client.patch(
            f"/api/fleets/{fleet.id}",
            {"status": "cancelled"},
            "application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        schedule_mock.assert_not_called()


@override_settings(
    DISCORD_GUILD_ID=1041384161505722368,
    DISCORD_AARS_FORUM_CHANNEL_ID=1069380111897481256,
)
class FleetClosedCopyTestCase(TestCase):
    def test_eve_mail_has_aar_and_roam_report_not_srp(self):
        payload = render_fleet_closed(
            {
                "fleet_id": 1234,
                "fleet_type": "Non Strategic Operation",
                "location_name": "Amo",
                "objective": "Roam Hevrice",
                "time_window": "2026-08-30 15:01–19:01 EVE",
                "member_count": 42,
                "aar_url": (
                    "https://discord.com/channels/"
                    "1041384161505722368/1069380111897481256"
                ),
                "roam_report_url": (
                    "https://www.roamreport.com/f/csel3qi23akg00dfkju0"
                ),
            }
        )
        body = payload["eve_mail_body"]
        self.assertEqual(
            payload["subject"],
            "Fleet 1234 closed — AAR and roam report",
        )
        self.assertIn("Your fleet is closed.", body)
        self.assertIn("1) Write your AAR", body)
        self.assertIn(
            "https://discord.com/channels/1041384161505722368/1069380111897481256",
            body,
        )
        self.assertIn("2) Roam report", body)
        self.assertIn(
            "https://www.roamreport.com/f/csel3qi23akg00dfkju0",
            body,
        )
        self.assertNotIn("Review SRP", body)
        self.assertNotIn("/fleets/history/", body)
        self.assertIn("— BearThatCares", body)

    def test_missing_roam_report_fallback(self):
        payload = render_fleet_closed(
            {
                "fleet_id": 1,
                "fleet_type": "Training Operation",
                "location_name": "Amo",
                "member_count": 1,
                "aar_url": "https://discord.com/channels/1/2",
                "roam_report_url": "",
            }
        )
        self.assertIn(
            "Could not generate automatically", payload["eve_mail_body"]
        )
        self.assertIn("https://www.roamreport.com", payload["eve_mail_body"])
