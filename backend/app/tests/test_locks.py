from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase

from app.locks import single_flight


class SingleFlightTestCase(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_second_concurrent_caller_is_told_to_skip(self):
        with single_flight("test:lock", 60) as first:
            with single_flight("test:lock", 60) as second:
                self.assertTrue(first)
                self.assertFalse(second)
        with single_flight("test:lock", 60) as third:
            self.assertTrue(third)

    def test_does_not_release_a_lock_it_no_longer_owns(self):
        with single_flight("test:lock", 60):
            # Our TTL lapsed and another run took the lock.
            cache.set("test:lock", "someone-else", 60)
        self.assertEqual(cache.get("test:lock"), "someone-else")

    def test_cache_outage_runs_unguarded(self):
        with patch(
            "app.locks.cache.add", side_effect=ConnectionError("redis down")
        ):
            with single_flight("test:lock", 60) as acquired:
                self.assertTrue(acquired)
