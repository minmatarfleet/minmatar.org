from datetime import datetime, timezone

from django.test import SimpleTestCase

from timezones.fleet_time import (
    brackets_at,
    clean_codes,
    fleet_timezones,
    in_timezones,
)


def utc(*args) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


class FleetTimezonesTests(SimpleTestCase):
    def test_a_start_can_be_two_timezones(self):
        # Sat 01:00 EVE: 21:00 in New York, 02:00 in Berlin.
        self.assertEqual(
            fleet_timezones(utc(2030, 11, 2, 1)), (["USTZ", "EUTZ+"], False)
        )

    def test_eu_evening(self):
        self.assertEqual(brackets_at(utc(2030, 11, 2, 20)), ["EUTZ"])

    def test_au_evening(self):
        # 09:00 EVE is 20:00 in Sydney (AEDT).
        self.assertEqual(brackets_at(utc(2030, 11, 2, 9)), ["AUTZ"])

    def test_nobodys_evening_gets_the_nearest_evening(self):
        # 16:00 EVE: 17:00 Berlin, 11:00 New York, 03:00 Sydney.
        self.assertEqual(
            fleet_timezones(utc(2030, 11, 3, 16)), (["EUTZ"], True)
        )

    def test_daylight_saving_moves_the_window_in_eve_time(self):
        # 22:00 EVE is 18:00 in New York in summer, 17:00 in winter.
        self.assertIn("USTZ", brackets_at(utc(2030, 7, 6, 22)))
        self.assertNotIn("USTZ", brackets_at(utc(2030, 12, 7, 22)))


class InTimezonesTests(SimpleTestCase):
    def test_overlap(self):
        self.assertTrue(in_timezones(["EUTZ", "USTZ"], ["USTZ"]))
        self.assertFalse(in_timezones(["EUTZ"], ["USTZ", "EUTZ+"]))

    def test_unknown_pilots_are_in(self):
        self.assertTrue(in_timezones([], ["USTZ"]))
        self.assertTrue(in_timezones(None, ["USTZ"]))

    def test_clean_codes_keeps_known_codes_in_order(self):
        self.assertEqual(
            clean_codes(["EUTZ", "nope", "USTZ", "EUTZ"]), ["USTZ", "EUTZ"]
        )
