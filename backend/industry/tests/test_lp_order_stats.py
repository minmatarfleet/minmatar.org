"""Tests for the rolling LP buyback order stats endpoint."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from industry.models import (
    IndustryLoyaltyPoint,
    IndustryLoyaltyPointMarketOrder,
    IndustryLoyaltyPointMarketOrderClaim,
)

User = get_user_model()
Order = IndustryLoyaltyPointMarketOrder


class LpOrderStatsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="lp-stats", password="x")
        self.tlf, _ = IndustryLoyaltyPoint.objects.update_or_create(
            corporation_id=1000182,
            defaults={"name": "Tribal Liberation Force", "is_active": True},
        )
        self.other, _ = IndustryLoyaltyPoint.objects.update_or_create(
            corporation_id=1000179,
            defaults={"name": "24th Imperial Crusade", "is_active": True},
        )
        self.now = timezone.now()

    def _order(
        self,
        *,
        tier=Order.Tier.STANDARD,
        status=Order.Status.COMPLETED,
        quantity=100_000,
        isk_per_lp=800,
        age=timedelta(days=2),
        close=timedelta(hours=10),
        currency=None,
    ):
        order = Order.objects.create(
            loyalty_point=currency or self.tlf,
            side=Order.Side.SELL,
            quantity=quantity,
            isk_per_lp=isk_per_lp,
            tier=tier,
            status=status,
            created_by=self.user,
        )
        created_at = self.now - age
        completed_at = (
            created_at + close if status == Order.Status.COMPLETED else None
        )
        # created_at is auto_now_add; backdate with a queryset update.
        Order.objects.filter(pk=order.pk).update(
            created_at=created_at, completed_at=completed_at
        )
        return order

    def _stats(self, **params):
        response = self.client.get(
            "/api/industry/loyalty/stats",
            {"loyalty_point_id": self.tlf.pk, **params},
        )
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_empty_window(self):
        body = self._stats()
        self.assertEqual(body["days"], 30)
        self.assertEqual(body["orders"], 0)
        self.assertIsNone(body["avg_close_seconds"])
        self.assertIsNone(body["avg_isk_per_lp"])
        self.assertEqual(body["express"]["orders"], 0)

    def test_tiers_close_time_and_weighted_price(self):
        self._order(
            quantity=100_000, isk_per_lp=800, close=timedelta(hours=40)
        )
        self._order(
            quantity=300_000, isk_per_lp=840, close=timedelta(hours=60)
        )
        self._order(
            tier=Order.Tier.EXPRESS,
            quantity=200_000,
            isk_per_lp=760,
            close=timedelta(hours=6),
        )
        # Still open: counts as an order, not toward close time or price.
        self._order(status=Order.Status.OPEN, isk_per_lp=1)

        body = self._stats()
        self.assertEqual(body["orders"], 4)
        self.assertEqual(body["completed"], 3)
        self.assertEqual(body["avg_close_seconds"], 106 * 3600 // 3)
        # (100k*800 + 300k*840 + 200k*760) / 600k
        self.assertEqual(body["avg_isk_per_lp"], 806.7)

        self.assertEqual(body["standard"]["orders"], 3)
        self.assertEqual(body["standard"]["completed"], 2)
        self.assertEqual(body["standard"]["avg_close_seconds"], 50 * 3600)
        self.assertEqual(body["standard"]["avg_isk_per_lp"], 830.0)
        self.assertEqual(body["express"]["orders"], 1)
        self.assertEqual(body["express"]["avg_close_seconds"], 6 * 3600)
        self.assertEqual(body["express"]["avg_isk_per_lp"], 760.0)

    def test_cancelled_orders_are_excluded(self):
        self._order(tier=Order.Tier.EXPRESS, close=timedelta(hours=5))
        self._order(tier=Order.Tier.EXPRESS, status=Order.Status.CANCELLED)

        body = self._stats()
        self.assertEqual(body["orders"], 1)
        self.assertEqual(body["express"]["orders"], 1)
        self.assertEqual(body["express"]["avg_close_seconds"], 5 * 3600)

    def test_window_and_currency_filter(self):
        # Posted before the window, completed inside it: close time only.
        self._order(age=timedelta(days=35), close=timedelta(days=6))
        # Completed before the window: ignored.
        self._order(age=timedelta(days=60), close=timedelta(days=1))
        self._order(currency=self.other)

        body = self._stats()
        self.assertEqual(body["orders"], 0)
        self.assertEqual(body["completed"], 1)
        self.assertEqual(body["avg_close_seconds"], 6 * 86400)

        body = self._stats(days=90)
        self.assertEqual(body["orders"], 2)

    def test_rejects_bad_window(self):
        response = self.client.get("/api/industry/loyalty/stats", {"days": 0})
        self.assertEqual(response.status_code, 422)

    def _claim(self, order, user, *, after, amount=None):
        claim = IndustryLoyaltyPointMarketOrderClaim.objects.create(
            order=order,
            claimed_by=user,
            amount=amount or order.quantity,
        )
        order.refresh_from_db()
        IndustryLoyaltyPointMarketOrderClaim.objects.filter(
            pk=claim.pk
        ).update(created_at=order.created_at + after)
        return claim

    def test_medians_split_wait_at_first_claim(self):
        converter = User.objects.create_user(username="lp-converter")
        fast = self._order(
            quantity=200_000, age=timedelta(days=3), close=timedelta(hours=4)
        )
        slow = self._order(
            quantity=100_000, age=timedelta(days=3), close=timedelta(hours=50)
        )
        self._claim(fast, converter, after=timedelta(hours=1))
        self._claim(slow, converter, after=timedelta(hours=40))

        body = self._stats()
        self.assertEqual(body["median_close_seconds"], 27 * 3600)
        self.assertEqual(body["paid_within_day"], 1)
        self.assertEqual(body["lp_completed"], 300_000)
        self.assertEqual(body["isk_completed"], 300_000 * 800)
        # Posted -> claimed: 1h and 40h; claimed -> paid: 3h and 10h.
        self.assertEqual(body["median_claim_seconds"], int(20.5 * 3600))
        self.assertEqual(body["median_settle_seconds"], int(6.5 * 3600))

        [row] = body["converters"]
        self.assertEqual(row["user_id"], converter.pk)
        self.assertEqual(row["name"], "lp-converter")
        self.assertEqual(row["orders"], 2)
        self.assertEqual(row["lp"], 300_000)
        self.assertEqual(row["isk"], 300_000 * 800)
        self.assertEqual(row["median_settle_seconds"], int(6.5 * 3600))

    def test_weekly_spans_twelve_weeks_ending_this_week(self):
        self._order(
            quantity=400_000, age=timedelta(hours=3), close=timedelta(hours=1)
        )
        self._order(quantity=100_000, age=timedelta(days=200))

        weekly = self._stats()["weekly"]
        self.assertEqual(len(weekly), 12)
        # This week, or last week right after Monday midnight.
        self.assertEqual(weekly[-1]["lp"] + weekly[-2]["lp"], 400_000)
        self.assertEqual(sum(w["lp"] for w in weekly), 400_000)
        self.assertLess(weekly[0]["week_start"], weekly[-1]["week_start"])
