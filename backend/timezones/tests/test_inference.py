from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase

from timezones.inference import (
    ACTIVITY,
    DECLARED,
    assess,
    count_evenings,
)

NEW_YORK = ZoneInfo("America/New_York")
LONDON = ZoneInfo("Europe/London")
BERLIN = ZoneInfo("Europe/Berlin")
SYDNEY = ZoneInfo("Australia/Sydney")
START = datetime(2026, 8, 1)


def nights(zone, hour, count, minute=30, every=2, start=START):
    """``count`` evenings at ``hour`` local, ``every`` days apart."""
    return [
        (start + timedelta(days=day * every)).replace(
            hour=hour, minute=minute, tzinfo=zone
        )
        for day in range(count)
    ]


def busy(times, per_night=3):
    """A few killmails per session, as a real fight would leave."""
    return [
        t + timedelta(minutes=10 * i) for t in times for i in range(per_night)
    ]


class AssessTestCase(SimpleTestCase):
    def test_east_coast_pilot_who_flies_eu_afternoons_gets_both(self):
        events = busy(nights(NEW_YORK, 19, 24)) + busy(
            nights(NEW_YORK, 14, 15, start=START + timedelta(days=1))
        )
        result = assess(events, declared="US")
        self.assertEqual(result.home, "US")
        self.assertEqual(result.home_source, ACTIVITY)
        self.assertEqual(result.brackets, {"USTZ", "EUTZ"})

    def test_uk_night_owl_gets_eutz_plus(self):
        events = busy(nights(LONDON, 20, 20)) + busy(
            nights(LONDON, 23, 10, start=START + timedelta(days=1))
        )
        result = assess(events)
        self.assertEqual(result.home, "EU")
        self.assertEqual(result.brackets, {"EUTZ", "EUTZ+"})

    def test_eu_late_night_does_not_count_as_us_prime(self):
        # 01:00 Berlin is 19:00 the evening before in New York.
        events = busy(nights(BERLIN, 20, 25)) + busy(
            nights(BERLIN, 1, 15, minute=0, start=START + timedelta(days=1))
        )
        result = assess(events, declared="EU")
        self.assertEqual(result.home, "EU")
        self.assertIn("EUTZ+", result.brackets)
        self.assertNotIn("USTZ", result.brackets)

    def test_australian_evenings_make_an_au_home(self):
        result = assess(busy(nights(SYDNEY, 20, 20)))
        self.assertEqual(result.home, "AU")
        self.assertEqual(result.brackets, {"AUTZ"})

    def test_declared_prime_time_until_there_is_activity(self):
        result = assess([], declared="EU")
        self.assertEqual((result.home, result.home_source), ("EU", DECLARED))
        self.assertEqual(result.brackets, {"EUTZ"})
        self.assertIsNone(result.inferred_home)

    def test_crossover_codes_mean_what_applicants_meant(self):
        # The application form saves US afternoon players as EU_US.
        self.assertEqual(assess([], declared="EU_US").home, "US")
        self.assertEqual(assess([], declared="US_AP").home, "EU")

    def test_nothing_to_go_on_means_no_brackets(self):
        result = assess([])
        self.assertIsNone(result.home)
        self.assertEqual(result.brackets, frozenset())

    def test_an_unsure_model_defers_to_what_the_pilot_declared(self):
        # Two killmails at 17:00 UTC: EU evening or US lunchtime.
        events = [
            datetime(2026, 8, 3, 17, tzinfo=ZoneInfo("UTC")),
            datetime(2026, 8, 5, 17, tzinfo=ZoneInfo("UTC")),
        ]
        result = assess(events, declared="US")
        self.assertLess(result.inferred_confidence, 0.8)
        self.assertEqual((result.home, result.home_source), ("US", DECLARED))

    def test_a_held_role_needs_less_to_keep_than_to_earn(self):
        events = busy(nights(LONDON, 20, 27)) + busy(
            nights(LONDON, 23, 3, start=START + timedelta(days=1))
        )
        self.assertNotIn("EUTZ+", assess(events).brackets)
        self.assertIn("EUTZ+", assess(events, held={"EUTZ+"}).brackets)

    def test_evenings_stay_in_their_bracket_across_a_clock_change(self):
        # EU clocks went back on 25 October 2026.
        events = nights(BERLIN, 20, 10, every=1, start=datetime(2026, 10, 20))
        self.assertEqual(count_evenings(events)["EU_prime"], 10)

    def test_one_long_night_is_one_evening(self):
        events = [
            datetime(2026, 8, 3, 23, 30, tzinfo=BERLIN),
            datetime(2026, 8, 4, 0, 30, tzinfo=BERLIN),
            datetime(2026, 8, 4, 1, 30, tzinfo=BERLIN),
        ]
        self.assertEqual(count_evenings(events)["EU_late"], 1)
