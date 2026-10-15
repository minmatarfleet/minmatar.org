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

    def test_token_cost_matches_esi(self):
        self.assertEqual(esi_gate.token_cost(200), 2)
        self.assertEqual(esi_gate.token_cost(304), 1)
        self.assertEqual(esi_gate.token_cost(429), 5)
        self.assertEqual(esi_gate.token_cost(500), 0)

    def test_a_429_pauses_one_character_and_leaves_the_budget_clock(self):
        esi_gate.error_budget()
        reset_before = cache.get(esi_gate.ERROR_BUDGET_RESET_KEY)

        esi_gate.note_call(
            "char-notification",
            1,
            429,
            {"Retry-After": "90"},
        )

        self.assertFalse(esi_gate.can_spend("char-notification", 1))
        self.assertTrue(esi_gate.can_spend("char-notification", 2))
        self.assertGreaterEqual(
            esi_gate.pause_remaining("char-notification", 1), 30
        )
        self.assertEqual(
            cache.get(esi_gate.ERROR_BUDGET_RESET_KEY), reset_before
        )

    def test_a_4xx_costs_five_tokens(self):
        esi_gate.note_call("char-notification", 7, 403, {})
        # 15-token bucket, 20% reserve, so 12 tokens are spendable. One 4xx
        # is 5 of them; two more would pass, a third would not.
        esi_gate.note_call("char-notification", 7, 403, {})
        self.assertTrue(esi_gate.can_spend("char-notification", 7))
        esi_gate.note_call("char-notification", 7, 403, {})
        self.assertFalse(esi_gate.can_spend("char-notification", 7))

    def test_a_420_pauses_every_group(self):
        esi_gate.note_call(
            "char-notification",
            1,
            420,
            {"X-Esi-Error-Limit-Reset": "45"},
        )
        self.assertFalse(esi_gate.can_spend("char-killmail", 99))
        self.assertFalse(esi_gate.can_spend("affiliation", 1))

    def test_notification_etags_are_remembered(self):
        esi_gate.note_call(
            "char-notification",
            5,
            200,
            {"ETag": 'W/"def"'},
        )
        self.assertEqual(esi_gate.notification_etag(5), 'W/"def"')
