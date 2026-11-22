"""parse_esi_date accepts every ISO shape ESI sends (Sentry MINMATAR-CELERY-P0/NF)."""

from datetime import datetime, timedelta, timezone as dt_timezone

from django.test import SimpleTestCase

from eveonline.helpers.esi import parse_esi_date

UTC = dt_timezone.utc


class ParseEsiDateTest(SimpleTestCase):
    def test_two_digit_fraction(self):
        self.assertEqual(
            parse_esi_date("2026-10-01T16:01:03.54Z"),
            datetime(2026, 10, 1, 16, 1, 3, 540000, tzinfo=UTC),
        )

    def test_two_digit_fraction_with_offset(self):
        self.assertEqual(
            parse_esi_date("2024-07-07T15:38:08.97+00:00"),
            datetime(2024, 7, 7, 15, 38, 8, 970000, tzinfo=UTC),
        )

    def test_one_and_seven_digit_fractions(self):
        self.assertEqual(
            parse_esi_date("2026-10-01T16:01:03.5Z").microsecond, 500000
        )
        self.assertEqual(
            parse_esi_date("2026-10-01T16:01:03.1234567Z").microsecond, 123456
        )

    def test_three_and_six_digit_fractions(self):
        self.assertEqual(
            parse_esi_date("2026-10-01T16:01:03.540Z").microsecond, 540000
        )
        self.assertEqual(
            parse_esi_date("2026-10-01T16:01:03.540001Z").microsecond, 540001
        )

    def test_z_suffix_without_fraction(self):
        self.assertEqual(
            parse_esi_date("2026-10-01T16:01:03Z"),
            datetime(2026, 10, 1, 16, 1, 3, tzinfo=UTC),
        )

    def test_naive_string_is_utc(self):
        self.assertEqual(
            parse_esi_date("2026-10-01T16:01:03"),
            datetime(2026, 10, 1, 16, 1, 3, tzinfo=UTC),
        )

    def test_other_offset_is_kept(self):
        dt = parse_esi_date("2026-10-01T18:01:03.5+02:00")
        self.assertEqual(dt.utcoffset(), timedelta(hours=2))
        self.assertEqual(
            dt, datetime(2026, 10, 1, 16, 1, 3, 500000, tzinfo=UTC)
        )

    def test_datetime_instances(self):
        aware = datetime(2026, 10, 1, 16, 1, 3, tzinfo=UTC)
        self.assertIs(parse_esi_date(aware), aware)
        naive = parse_esi_date(datetime(2026, 10, 1, 16, 1, 3))
        self.assertIsNotNone(naive.tzinfo)

    def test_empty_is_none(self):
        self.assertIsNone(parse_esi_date(None))
        self.assertIsNone(parse_esi_date(""))

    def test_garbage_still_raises(self):
        with self.assertRaises(ValueError):
            parse_esi_date("not a date")
