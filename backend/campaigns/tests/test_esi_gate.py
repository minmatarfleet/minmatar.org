"""The ESI budget gate must never spend the whole bucket."""

from django.core.cache import cache
from django.test import TestCase

from campaigns.services import esi_gate


class BudgetTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_an_unknown_group_is_never_blocked(self):
        self.assertTrue(esi_gate.can_spend("affiliation", 1))
        self.assertTrue(esi_gate.spend("affiliation", 1))

    def test_a_bucket_is_held_open_at_the_reserve(self):
        """char-notification allows 15 tokens; we stop at 12."""
        allowed = 0
        for _ in range(20):
            if not esi_gate.spend("char-notification", 42):
                break
            allowed += 1

        self.assertLessEqual(allowed * 2, 12)
        self.assertFalse(esi_gate.can_spend("char-notification", 42))

    def test_buckets_are_per_character(self):
        for _ in range(10):
            esi_gate.spend("char-notification", 1)
        self.assertFalse(esi_gate.can_spend("char-notification", 1))
        self.assertTrue(esi_gate.can_spend("char-notification", 2))

    def test_a_low_error_budget_stops_everything(self):
        cache.set(esi_gate.ERROR_BUDGET_KEY, 5, 120)
        cache.set(esi_gate.ERROR_BUDGET_RESET_KEY, 9999999999, 120)
        self.assertFalse(esi_gate.can_spend("char-killmail", 1))

    def test_errors_eat_the_app_wide_budget(self):
        before = esi_gate.error_budget()
        esi_gate.record_error()
        self.assertLess(esi_gate.error_budget(), before)

    def test_esi_headers_are_believed_over_our_own_ledger(self):
        esi_gate.observe_headers(
            {"X-Esi-Error-Limit-Remain": "7", "X-Esi-Error-Limit-Reset": "45"}
        )
        self.assertEqual(esi_gate.error_budget(), 7)

    def test_a_header_without_a_reset_still_sticks_for_the_minute(self):
        esi_gate.observe_headers({"X-Esi-Error-Limit-Remain": "3"})
        self.assertEqual(esi_gate.error_budget(), 3)
        self.assertFalse(esi_gate.can_spend("char-notification", 1))

    def test_snapshot_reports_what_the_kpi_panel_needs(self):
        report = esi_gate.snapshot()
        self.assertIn("error_budget", report)
        self.assertIn("char-notification", report["groups"])
