"""EVE time helpers (app.eve_time) and parity with the copies they replace."""

from datetime import date, datetime, timedelta
from datetime import timezone as dt_timezone
from unittest.mock import patch

from django.test import SimpleTestCase
from django.utils import timezone

from app.eve_time import as_eve_time, eve_now, month_bounds, month_key
from campaigns.helpers import campaign_day
from tribes.reports.queries.common import period_window
from tribes.reports.types import PeriodBounds

UTC = dt_timezone.utc


def _old_eve_time(value):
    """corporations about.py / timezones.py ``_eve_time``."""
    aware = timezone.make_aware(value) if timezone.is_naive(value) else value
    return aware.astimezone(UTC)


def _old_month_key(value):
    """alliance.helpers.health ``_month_key``."""
    return f"{value.year:04d}-{value.month:02d}"


def _old_calendar_month_bounds(now):
    """fleets commander metrics ``_calendar_month_bounds`` at ``now``."""
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


EDGES = [
    datetime(2026, 12, 31, 23, 59, 59, 999999, tzinfo=UTC),
    datetime(2027, 1, 1, 0, 0, tzinfo=UTC),
    datetime(2028, 2, 29, 23, 59, 59, tzinfo=UTC),
    datetime(2028, 3, 1, 0, 0, tzinfo=UTC),
    datetime(2027, 2, 28, 12, 0, tzinfo=UTC),
    datetime(2026, 11, 1, 0, 0, tzinfo=UTC),
    datetime(2026, 11, 1, 10, 59, tzinfo=UTC),
    datetime(2026, 11, 1, 11, 0, tzinfo=UTC),
]


class MonthKeyTest(SimpleTestCase):
    def test_december_to_january(self):
        self.assertEqual(month_key(EDGES[0]), "2026-12")
        self.assertEqual(month_key(EDGES[1]), "2027-01")

    def test_leap_february(self):
        self.assertEqual(month_key(EDGES[2]), "2028-02")
        self.assertEqual(month_key(EDGES[3]), "2028-03")

    def test_dates(self):
        self.assertEqual(month_key(date(2026, 1, 31)), "2026-01")

    def test_naive_is_read_as_utc_and_offsets_convert(self):
        self.assertEqual(month_key(datetime(2026, 10, 31, 23, 30)), "2026-10")
        plus_two = dt_timezone(timedelta(hours=2))
        # 01:00 on Nov 1 at UTC+2 is still October in EVE.
        self.assertEqual(
            month_key(datetime(2026, 11, 1, 1, 0, tzinfo=plus_two)), "2026-10"
        )

    def test_parity_with_old_copies(self):
        for value in EDGES:
            self.assertEqual(month_key(value), _old_month_key(value))
            self.assertEqual(month_key(value), value.strftime("%Y-%m"))
            self.assertEqual(
                month_key(value), _old_eve_time(value).strftime("%Y-%m")
            )


class MonthBoundsTest(SimpleTestCase):
    def test_half_open_december(self):
        start, end = month_bounds(EDGES[0])
        self.assertEqual(start, datetime(2026, 12, 1, tzinfo=UTC))
        self.assertEqual(end, datetime(2027, 1, 1, tzinfo=UTC))
        self.assertEqual(month_bounds(end)[0], end)

    def test_february(self):
        self.assertEqual(
            month_bounds(date(2028, 2, 15))[1],
            datetime(2028, 3, 1, tzinfo=UTC),
        )
        self.assertEqual(
            month_bounds(date(2027, 2, 15))[1],
            datetime(2027, 3, 1, tzinfo=UTC),
        )

    def test_naive_input(self):
        self.assertEqual(
            month_bounds(datetime(2026, 11, 30, 23, 0))[0],
            datetime(2026, 11, 1, tzinfo=UTC),
        )

    def test_default_is_now_and_matches_old_fleet_commander_bounds(self):
        for now in EDGES:
            with patch("django.utils.timezone.now", return_value=now):
                self.assertEqual(eve_now(), now)
                self.assertEqual(
                    month_bounds(), _old_calendar_month_bounds(now)
                )


class AsEveTimeTest(SimpleTestCase):
    def test_naive_and_aware(self):
        naive = datetime(2026, 11, 1, 10, 59)
        self.assertEqual(as_eve_time(naive), naive.replace(tzinfo=UTC))
        plus_two = dt_timezone(timedelta(hours=2))
        aware = datetime(2026, 11, 1, 13, 0, tzinfo=plus_two)
        self.assertEqual(
            as_eve_time(aware), datetime(2026, 11, 1, 11, 0, tzinfo=UTC)
        )
        self.assertEqual(as_eve_time(aware).tzinfo, UTC)

    def test_parity_with_old_copies(self):
        plus_two = dt_timezone(timedelta(hours=2))
        for value in EDGES + [
            datetime(2026, 11, 1, 1, 0),
            datetime(2026, 11, 1, 1, 0, tzinfo=plus_two),
        ]:
            self.assertEqual(as_eve_time(value), _old_eve_time(value))


class CalendarsStayDistinctTest(SimpleTestCase):
    """EVE months turn at 00:00 UTC; campaign days turn at 11:00 UTC."""

    def test_campaign_day_rollover_vs_eve_month(self):
        midnight, before, at = EDGES[5:8]
        self.assertEqual(month_key(midnight), "2026-11")
        self.assertEqual(month_key(before), "2026-11")
        self.assertEqual(campaign_day(midnight), date(2026, 10, 31))
        self.assertEqual(campaign_day(before), date(2026, 10, 31))
        self.assertEqual(campaign_day(at), date(2026, 11, 1))

    def test_tribe_period_window_keeps_inclusive_end(self):
        start, end = period_window(
            PeriodBounds(
                label="October",
                start=date(2026, 10, 1),
                end=date(2026, 10, 31),
            )
        )
        self.assertEqual(start, datetime(2026, 10, 1, tzinfo=UTC))
        self.assertEqual(
            end, datetime(2026, 10, 31, 23, 59, 59, 999999, tzinfo=UTC)
        )
