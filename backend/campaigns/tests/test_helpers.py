"""Campaign days and weeks both turn over at 11:00 UTC."""

from datetime import date, datetime
from datetime import timezone as datetime_timezone

from django.test import TestCase

from campaigns.helpers import (
    campaign_day,
    campaign_week_start,
    day_bounds,
    week_bounds,
)
from campaigns.services.stats import prime_time_label


def moment(year, month, day, hour, minute=0):
    return datetime(
        year, month, day, hour, minute, tzinfo=datetime_timezone.utc
    )


class CampaignDayTests(TestCase):
    def test_before_eleven_belongs_to_the_previous_day(self):
        self.assertEqual(
            campaign_day(moment(2026, 9, 19, 10, 59)), date(2026, 9, 18)
        )

    def test_eleven_exactly_starts_the_new_day(self):
        self.assertEqual(
            campaign_day(moment(2026, 9, 19, 11, 0)), date(2026, 9, 19)
        )

    def test_late_evening_is_the_same_day(self):
        self.assertEqual(
            campaign_day(moment(2026, 9, 19, 23, 30)), date(2026, 9, 19)
        )

    def test_day_bounds_span_exactly_one_day(self):
        start, end = day_bounds(date(2026, 9, 19))
        self.assertEqual(start.hour, 11)
        self.assertEqual((end - start).days, 1)


class CampaignWeekTests(TestCase):
    def test_the_week_opens_on_thursday(self):
        # 2026-09-19 is a Saturday; its week opened Thursday the 17th.
        self.assertEqual(
            campaign_week_start(moment(2026, 9, 19, 12)), date(2026, 9, 17)
        )

    def test_thursday_morning_still_belongs_to_the_old_week(self):
        self.assertEqual(
            campaign_week_start(moment(2026, 9, 17, 10)), date(2026, 9, 10)
        )

    def test_thursday_at_eleven_opens_the_new_week(self):
        self.assertEqual(
            campaign_week_start(moment(2026, 9, 17, 11)), date(2026, 9, 17)
        )

    def test_week_bounds_span_seven_days(self):
        start, end = week_bounds(date(2026, 9, 17))
        self.assertEqual((end - start).days, 7)


class PrimeTimeTests(TestCase):
    def test_hours_map_to_a_timezone_label(self):
        self.assertEqual(prime_time_label(2), "AUTZ")
        self.assertEqual(prime_time_label(12), "EUTZ")
        self.assertEqual(prime_time_label(20), "USTZ")
