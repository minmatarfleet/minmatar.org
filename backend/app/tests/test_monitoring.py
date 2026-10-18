import os
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from sentry_sdk.utils import match_regex_list

from app import monitoring
from app.monitoring import (
    CRON_MONITORED_SCHEDULES,
    detect_component,
    dsn_for,
    tick_task_names,
    traces_sampler,
    unmonitored_schedules_pattern,
)


class ComponentTestCase(SimpleTestCase):
    def test_detects_the_process(self):
        self.assertEqual(
            detect_component(["celery", "-A", "app", "beat", "-l", "info"]),
            "beat",
        )
        self.assertEqual(
            detect_component(["celery", "-A", "app", "worker", "-Q", "feed"]),
            "worker",
        )
        self.assertEqual(detect_component(["gunicorn", "app.wsgi"]), "web")

    def test_celery_processes_share_the_celery_project(self):
        env = {"SENTRY_BACKEND_DSN": "backend", "SENTRY_CELERY_DSN": "celery"}
        with patch.dict(os.environ, env):
            self.assertEqual(dsn_for("web"), "backend")
            self.assertEqual(dsn_for("beat"), "celery")
            self.assertEqual(dsn_for("worker"), "celery")
        with patch.dict(os.environ, {"SENTRY_BACKEND_DSN": "backend"}):
            os.environ.pop("SENTRY_CELERY_DSN", None)
            self.assertEqual(dsn_for("worker"), "backend")


class SamplingTestCase(SimpleTestCase):
    def test_ticks_are_sampled_lightly(self):
        self.assertIn("feed.tasks.poll_zkill_r2z2", tick_task_names())
        self.assertIn("app.tasks.monitor_queue_health", tick_task_names())
        self.assertNotIn(
            "market.tasks.fetch_eve_market_contracts", tick_task_names()
        )
        tick = {"celery_job": {"task": "feed.tasks.poll_zkill_r2z2"}}
        other = {
            "celery_job": {"task": "market.tasks.fetch_eve_market_contracts"}
        }
        self.assertEqual(traces_sampler(tick), 0.02)
        self.assertEqual(traces_sampler(other), 0.2)
        self.assertEqual(traces_sampler({"wsgi_environ": {}}), 0.2)

    def test_follows_the_parent_decision(self):
        self.assertEqual(traces_sampler({"parent_sampled": True}), 1.0)
        self.assertEqual(traces_sampler({"parent_sampled": False}), 0.0)

    def test_rates_come_from_the_environment(self):
        with patch.dict(
            os.environ,
            {
                "SENTRY_TRACES_SAMPLE_RATE": "0.5",
                "SENTRY_TICK_TRACES_SAMPLE_RATE": "0",
            },
        ):
            self.assertEqual(traces_sampler({}), 0.5)
            self.assertEqual(
                traces_sampler(
                    {"celery_job": {"task": "feed.tasks.poll_zkill_r2z2"}}
                ),
                0.0,
            )


class CronMonitorTestCase(SimpleTestCase):
    def test_only_listed_schedules_are_monitored(self):
        excluded = [unmonitored_schedules_pattern()]
        for name in CRON_MONITORED_SCHEDULES:
            with self.subTest(name):
                self.assertFalse(match_regex_list(name, excluded))
        for name in ("[Misc] Check Fleets", "[Feed] Poll zKill R2Z2"):
            with self.subTest(name):
                self.assertTrue(match_regex_list(name, excluded))


class TaskSignalsTestCase(SimpleTestCase):
    def test_tags_the_queue(self):
        with patch("app.monitoring.sentry_sdk.set_tag") as set_tag:
            monitoring.tag_task_run(
                SimpleNamespace(delivery_info={"routing_key": "market"})
            )
            monitoring.tag_task_run(SimpleNamespace(delivery_info=None))
        set_tag.assert_called_once_with("celery.queue", "market")

    def test_metrics_never_raise(self):
        with patch(
            "app.monitoring.sentry_sdk.metrics.count", side_effect=RuntimeError
        ):
            monitoring.record_task_skip("t", "cooldown")
        with patch(
            "app.monitoring.sentry_sdk.metrics.gauge", side_effect=RuntimeError
        ):
            monitoring.gauge("g", 1, queue="celery")
