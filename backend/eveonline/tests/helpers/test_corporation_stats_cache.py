from unittest.mock import patch

from django.core.cache import cache
from django.test import Client

from app.test import TestCase
from eveonline.helpers.corporations import stats_cache
from eveonline.models import EveCorporation
from eveonline.tasks.corporations import refresh_corporation_profile_stats


class CorporationStatsCacheTestCase(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.client = Client()
        self.corporation = EveCorporation.objects.create(
            corporation_id=98726134, name="Rattini Tribe"
        )

    def test_miss_queues_one_refresh_and_never_computes_inline(self):
        with patch.object(
            refresh_corporation_profile_stats, "apply_async"
        ) as queued, patch.object(
            stats_cache, "compute_corporation_stats"
        ) as compute:
            self.assertIsNone(stats_cache.corporation_stats(98726134))
            self.assertIsNone(stats_cache.corporation_stats(98726134))
        queued.assert_called_once_with(args=[98726134], queue="eveonline")
        compute.assert_not_called()

    def test_hit_serves_cached_stats(self):
        stats_cache.refresh_corporation_stats(self.corporation)
        with patch.object(stats_cache, "compute_corporation_stats") as compute:
            stats = stats_cache.corporation_stats(98726134)
        compute.assert_not_called()
        self.assertLessEqual(
            {
                "timezone_distribution",
                "weekday_distribution",
                "public_summary",
                "application_process",
                "member_activity",
                "declared_by_user",
                "observed_by_user",
                "human_count",
                "about",
                "member_facts",
            },
            set(stats),
        )

    def test_task_refreshes_one_corporation(self):
        self.assertEqual(1, refresh_corporation_profile_stats(98726134))
        self.assertIsNotNone(
            cache.get("corporation_profile_stats:v2:98726134")
        )

    def test_cache_outage_degrades_to_no_stats(self):
        with patch(
            "app.cache.cache.get",
            side_effect=ConnectionError("redis down"),
        ), patch(
            "app.cache.cache.add",
            side_effect=ConnectionError("redis down"),
        ):
            self.assertIsNone(stats_cache.corporation_stats(98726134))

    def test_members_endpoint_never_computes_stats_inline(self):
        self.make_superuser()
        with patch.object(
            refresh_corporation_profile_stats, "apply_async"
        ), patch.object(stats_cache, "compute_corporation_stats") as compute:
            response = self.client.get(
                "/api/eveonline/corporations/corporations/98726134/members",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            )
        self.assertEqual(200, response.status_code)
        compute.assert_not_called()
