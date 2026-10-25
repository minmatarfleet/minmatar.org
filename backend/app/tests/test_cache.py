from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import SimpleTestCase

from app import cache as app_cache
from app.cache import CachedRollup
from app.test import TestCase
from eveonline.helpers.corporations import stats_cache
from industry.helpers import product_insights
from market.endpoints import cache as market_cache
from market.helpers import (
    inferred_sales_monthly,
    inferred_sales_monthly_volume,
)
from tribes.helpers import about, showcase

DOWN = ConnectionError("redis down")


def _cache_down():
    """Every cache call raises, as with Redis unreachable."""
    return patch.multiple(
        "app.cache.cache",
        get=MagicMock(side_effect=DOWN),
        set=MagicMock(side_effect=DOWN),
        add=MagicMock(side_effect=DOWN),
        delete=MagicMock(side_effect=DOWN),
    )


class CachedRollupKeysTestCase(SimpleTestCase):
    """Ported rollups keep their keys and TTLs, so warm caches survive."""

    def test_corporation_stats(self):
        rollup = stats_cache.STATS
        self.assertEqual(
            rollup.key(corporation_id=7), "corporation_profile_stats:v3:7"
        )
        self.assertEqual(
            rollup.lock_key(corporation_id=7),
            "corporation_profile_stats:refreshing:7",
        )
        self.assertEqual((rollup.ttl, rollup.lock_ttl), (6 * 3600, 600))

    def test_product_insights(self):
        rollup = product_insights.INSIGHTS
        self.assertEqual(
            rollup.key(product_id=5), "industry_product_insights:v3:5"
        )
        self.assertEqual(
            rollup.lock_key(product_id=5),
            "industry_product_insights:refreshing",
        )
        self.assertEqual((rollup.ttl, rollup.lock_ttl), (6 * 3600, 600))

    def test_tribe_about(self):
        rollup = about.ABOUT
        self.assertEqual(rollup.key(tribe_id=3), "tribes:about:v2:3")
        self.assertEqual(
            rollup.lock_key(tribe_id=3), "tribes:about:refreshing:3"
        )
        self.assertEqual((rollup.ttl, rollup.lock_ttl), (6 * 3600, 600))

    def test_tribe_showcase_key_is_versioned(self):
        rollup = showcase.SHOWCASE
        self.assertEqual(
            rollup.key(group_id=4, period="30d"), "tribes:showcase:v1:4:30d"
        )
        self.assertEqual(rollup.ttl, 3600)

    def test_market_monthly(self):
        rollup = inferred_sales_monthly.MONTHLY
        params = {"location_id": 1, "year": 2026, "month": 8}
        self.assertEqual(
            rollup.key(using_suffix="", **params),
            "market:inferred_sales_monthly:1:2026-08",
        )
        self.assertEqual(
            rollup.key(using_suffix=":using:production_readonly", **params),
            "market:inferred_sales_monthly:1:2026-08:using:production_readonly",
        )
        self.assertEqual(
            inferred_sales_monthly_volume.VOLUME.key(
                using_suffix="", **params
            ),
            "market:inferred_sales_monthly_volume:1:2026-08",
        )


class GetOrQueueTestCase(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.enqueue = MagicMock()
        self.rollup = CachedRollup(
            key="test:rollup:v1:{thing_id}",
            ttl=60,
            lock_key="test:rollup:refreshing:{thing_id}",
            lock_ttl=60,
            enqueue=self.enqueue,
        )

    def test_concurrent_misses_queue_one_refresh(self):
        self.assertIsNone(self.rollup.get_or_queue(thing_id=1))
        self.assertIsNone(self.rollup.get_or_queue(thing_id=1))
        self.enqueue.assert_called_once_with(thing_id=1)

    def test_store_serves_and_releases_the_lock(self):
        self.rollup.get_or_queue(thing_id=1)
        self.rollup.store({"n": 1}, thing_id=1)
        self.assertEqual(self.rollup.get_or_queue(thing_id=1), {"n": 1})
        self.assertIsNone(cache.get("test:rollup:refreshing:1"))

    def test_failed_enqueue_releases_the_lock(self):
        self.enqueue.side_effect = ConnectionError("broker down")
        self.assertIsNone(self.rollup.get_or_queue(thing_id=1))
        self.assertIsNone(self.rollup.get_or_queue(thing_id=1))
        self.assertEqual(self.enqueue.call_count, 2)

    def test_cache_outage_reads_as_a_miss(self):
        with _cache_down():
            self.assertIsNone(self.rollup.get_or_queue(thing_id=1))
            self.rollup.store({"n": 1}, thing_id=1)
        self.enqueue.assert_not_called()


class GetOrComputeTestCase(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.rollup = CachedRollup(
            key="test:light:{thing_id}",
            ttl=60,
            lock_key="test:light:{thing_id}:computing",
            lock_ttl=60,
        )
        self.compute = MagicMock(return_value={"n": 1})

    def test_miss_computes_once_then_serves_the_cache(self):
        self.assertEqual(
            self.rollup.get_or_compute(self.compute, thing_id=1), {"n": 1}
        )
        self.assertEqual(
            self.rollup.get_or_compute(self.compute, thing_id=1), {"n": 1}
        )
        self.compute.assert_called_once()
        self.assertIsNone(cache.get("test:light:1:computing"))

    def test_lock_released_when_compute_raises(self):
        self.compute.side_effect = ValueError("boom")
        with self.assertRaises(ValueError):
            self.rollup.get_or_compute(self.compute, thing_id=1)
        self.assertIsNone(cache.get("test:light:1:computing"))

    def test_waits_for_the_caller_holding_the_lock(self):
        cache.add("test:light:1:computing", True, 60)

        def other_caller_finishes(seconds):
            del seconds
            cache.set("test:light:1", {"n": 2}, 60)

        with patch("app.cache.time.sleep", side_effect=other_caller_finishes):
            value = self.rollup.get_or_compute(self.compute, thing_id=1)
        self.assertEqual(value, {"n": 2})
        self.compute.assert_not_called()

    def test_computes_itself_when_the_holder_never_finishes(self):
        cache.add("test:light:1:computing", True, 60)
        value = self.rollup.get_or_compute(
            self.compute, wait_seconds=0, thing_id=1
        )
        self.assertEqual(value, {"n": 1})

    def test_cache_outage_computes_without_waiting(self):
        with _cache_down(), patch("app.cache.time.sleep") as sleep:
            value = self.rollup.get_or_compute(self.compute, thing_id=1)
        self.assertEqual(value, {"n": 1})
        sleep.assert_not_called()

    def test_ttl_override(self):
        with patch.object(app_cache, "cache_set") as cache_set:
            self.rollup.get_or_compute(self.compute, ttl=5, thing_id=1)
        cache_set.assert_called_once_with("test:light:1", {"n": 1}, 5)


class MarketCacheOutageTestCase(TestCase):
    def test_get_cached_view_still_answers_when_redis_is_down(self):
        @market_cache.get_cached(key_suffix="test-outage")
        def view(request):
            del request
            return {"ok": True}

        with _cache_down():
            self.assertEqual(view(None), {"ok": True})

    def test_get_cached_keeps_its_key_and_timeout(self):
        calls = []

        @market_cache.get_cached(key_suffix=lambda req, x: f"k:{x}")
        def view(request, x):
            del request
            calls.append(x)
            return [x]

        cache.clear()
        self.assertEqual(view(None, 3), [3])
        self.assertEqual(view(None, 3), [3])
        self.assertEqual(calls, [3])
        self.assertEqual(cache.get("market:api:k:3"), [3])

    def test_monthly_report_endpoint_survives_a_cache_outage(self):
        from eveonline.models import (  # pylint: disable=import-outside-toplevel
            EveLocation,
        )
        from market.models import (  # pylint: disable=import-outside-toplevel
            EveMarketInferredSale,
        )
        from market.tests.test_fitting_expectations import (  # pylint: disable=import-outside-toplevel
            _make_typed_eve_type,
        )

        location = EveLocation.objects.create(
            location_id=1022167642188,
            location_name="Amamake",
            short_name="Amamake",
            solar_system_id=30002537,
            solar_system_name="Amamake",
            market_active=True,
        )
        rifter = _make_typed_eve_type(587, "Rifter", 6, "Ship")
        EveMarketInferredSale.objects.create(
            location=location,
            item=rifter,
            quantity=2,
            price=Decimal("1000000"),
            inferred_at=datetime(2026, 8, 3, 12, tzinfo=dt_timezone.utc),
            reason=EveMarketInferredSale.REASON_PARTIAL_FILL,
        )
        cache.clear()
        cached = inferred_sales_monthly.build_monthly_response(
            1022167642188, 2026, 8
        )
        cache.clear()
        with _cache_down():
            uncached = inferred_sales_monthly.build_monthly_response(
                1022167642188, 2026, 8
            )
            rows = inferred_sales_monthly_volume.build_enriched_volume_rows(
                1022167642188, 2026, 8
            )
        self.assertEqual(cached, uncached)
        self.assertEqual(uncached["totals"]["units"], 2)
        self.assertEqual([r["type_id"] for r in rows], [587])
