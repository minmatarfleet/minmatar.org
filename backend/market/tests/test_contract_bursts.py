from datetime import timedelta

from django.test import SimpleTestCase
from django.utils import timezone

from market.helpers.contracts import (
    cluster_completion_bursts,
    estimate_contract_burst_size,
)


class ContractBurstHelpersTestCase(SimpleTestCase):
    def test_cluster_completion_bursts_by_gap(self):
        now = timezone.now()
        times = [
            now,
            now + timedelta(minutes=10),
            now + timedelta(minutes=20),
            now + timedelta(hours=2),
            now + timedelta(hours=2, minutes=5),
        ]
        self.assertEqual(
            cluster_completion_bursts(times, gap=timedelta(minutes=45)),
            [3, 2],
        )

    def test_estimate_prefers_multi_buy_median(self):
        # Solo restocks should not define fleet size when multi-buys exist.
        self.assertEqual(
            estimate_contract_burst_size([1, 1, 4, 4, 6]),
            4,
        )

    def test_estimate_falls_back_to_all_bursts(self):
        self.assertEqual(estimate_contract_burst_size([1, 1, 1]), 1)

    def test_estimate_empty(self):
        self.assertIsNone(estimate_contract_burst_size([]))
