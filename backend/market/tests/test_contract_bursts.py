from datetime import timedelta

from django.test import SimpleTestCase
from django.utils import timezone

from market.helpers.contracts import (
    cluster_completion_bursts,
    estimate_contract_burst_size,
    fleets_remaining_from_stock,
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

    def test_fleets_remaining_ceil(self):
        self.assertEqual(fleets_remaining_from_stock(5, 3), 2)
        self.assertEqual(fleets_remaining_from_stock(6, 3), 2)
        self.assertEqual(fleets_remaining_from_stock(0, 3), 0)
        self.assertIsNone(fleets_remaining_from_stock(5, None))
