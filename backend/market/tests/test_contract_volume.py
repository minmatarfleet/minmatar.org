from datetime import timedelta

from django.test import SimpleTestCase
from django.utils import timezone

from app.test import TestCase

from eveonline.models import EveLocation
from fittings.models import EveFitting
from market.helpers.contracts import (
    merge_stock_intervals,
    unstocked_pct_by_fitting,
)
from market.models import EveMarketContract


class MergeStockIntervalsTestCase(SimpleTestCase):
    def test_merges_overlap_and_skips_empty(self):
        now = timezone.now()
        a = now - timedelta(days=20)
        b = now - timedelta(days=10)
        c = now - timedelta(days=12)
        d = now - timedelta(days=5)
        merged = merge_stock_intervals(
            [
                (a, b),
                (c, d),
                (now, now - timedelta(days=1)),
            ]
        )
        self.assertEqual(merged, [(a, d)])


class UnstockedPctTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.location = EveLocation.objects.create(
            location_id=4242,
            location_name="Coverage test",
            solar_system_id=1,
            solar_system_name="Somewhere",
            market_active=True,
        )
        self.fitting = EveFitting.objects.create(
            name="[NVY-5] Coverage",
            ship_id=587,
            description="Coverage",
            eft_format="[Rifter, [NVY-5] Coverage]",
        )

    def test_never_listed_is_fully_unstocked(self):
        pct = unstocked_pct_by_fitting(
            location=self.location,
            fitting_ids=[self.fitting.id],
        )
        self.assertEqual({self.fitting.id: 100}, pct)

    def test_listed_half_the_window(self):
        now = timezone.now()
        EveMarketContract.objects.create(
            id=8001,
            location=self.location,
            fitting=self.fitting,
            status="outstanding",
            price=1.0,
            issuer_external_id=1,
            issued_at=now - timedelta(days=15),
            expires_at=now + timedelta(days=7),
        )
        pct = unstocked_pct_by_fitting(
            location=self.location,
            fitting_ids=[self.fitting.id],
        )
        self.assertEqual({self.fitting.id: 50}, pct)

    def test_overlapping_listings_do_not_double_count(self):
        now = timezone.now()
        EveMarketContract.objects.create(
            id=8002,
            location=self.location,
            fitting=self.fitting,
            status="finished",
            price=1.0,
            issuer_external_id=1,
            issued_at=now - timedelta(days=20),
            completed_at=now - timedelta(days=5),
        )
        EveMarketContract.objects.create(
            id=8003,
            location=self.location,
            fitting=self.fitting,
            status="outstanding",
            price=1.0,
            issuer_external_id=1,
            issued_at=now - timedelta(days=10),
            expires_at=now + timedelta(days=7),
        )
        pct = unstocked_pct_by_fitting(
            location=self.location,
            fitting_ids=[self.fitting.id],
        )
        # Union covers the last 20 of 30 days → 33% unstocked.
        self.assertEqual({self.fitting.id: 33}, pct)
