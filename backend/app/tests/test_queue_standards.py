"""The Celery queue standards (docs/architecture/celery-queues.md).

Every task routes through app.queues; nothing else picks a queue. The fast
lane holds only FAST_TASKS. Every queue has a production worker. Every task
is an AppTask, so every queue is deduped.
"""

import re
from pathlib import Path
from unittest import skipUnless

from celery_once import QueueOnce
from django.conf import settings
from django.test import SimpleTestCase

from app.celery import app
from app.monitoring import CRON_MONITORED_SCHEDULES
from app.queues import (
    FAST_LANE,
    FAST_TASKS,
    QUEUES,
    ROUTES,
    matched_route,
    queue_for_task,
)
from app.task_base import AppTask

BACKEND = Path(settings.BASE_DIR)
REPO = BACKEND.parent
COMPOSE_PROD = REPO / "docker-compose-prod.yml"
DEV_SH = REPO / "dev.sh"
# Third-party tasks that bring their own base class (QueueOnce).
THIRD_PARTY_BASES = ("eveuniverse.",)


def _tasks():
    app.loader.import_default_modules()
    return dict(app.tasks)


def _consumed_queues(text: str) -> set[str]:
    consumed = set()
    for queues in re.findall(r"celery -A app worker .*-Q ([\w,]+)", text):
        consumed.update(queues.split(","))
    return consumed


def _source_files():
    for path in BACKEND.rglob("*.py"):
        parts = set(path.relative_to(BACKEND).parts)
        if parts & {"migrations", "tests"} or path.name.startswith("test"):
            continue
        yield path


class QueueRoutingTestCase(SimpleTestCase):
    def test_every_task_has_a_route(self):
        unrouted = sorted(n for n in _tasks() if matched_route(n) is None)
        self.assertEqual(unrouted, [], "add a prefix to app.queues.ROUTES")

    def test_routes_point_at_declared_queues(self):
        self.assertEqual(sorted(set(ROUTES.values()) - set(QUEUES)), [])

    def test_fast_lane_is_exactly_the_listed_tasks(self):
        tasks = _tasks()
        self.assertEqual(sorted(FAST_TASKS - set(tasks)), [], "unknown task")
        on_fast_lane = {n for n in tasks if queue_for_task(n) == FAST_LANE}
        self.assertEqual(on_fast_lane, set(FAST_TASKS))

    def test_the_router_decides_for_celery(self):
        route = app.amqp.router.route(
            {}, "market.tasks.sync_character_attributed_orders", (), {}
        )
        self.assertEqual(route["queue"].name, "market")
        route = app.amqp.router.route(
            {}, "discord.outbox.post_discord_message_task", (), {}
        )
        self.assertEqual(route["queue"].name, FAST_LANE)

    def test_no_task_picks_its_own_queue(self):
        pinned = sorted(
            name
            for name, task in _tasks().items()
            if getattr(task, "queue", None)
        )
        self.assertEqual(pinned, [], "drop queue= from the decorator")

    def test_no_beat_entry_picks_a_queue(self):
        pinned = sorted(
            name
            for name, entry in settings.CELERYBEAT_SCHEDULE.items()
            if "queue" in entry.get("options", {})
        )
        self.assertEqual(pinned, [])

    def test_no_call_site_picks_a_queue_or_bypasses_the_base(self):
        forbidden = {
            "queue=": re.compile(r"\bqueue=[\"']"),
            "send_task(": re.compile(r"\bsend_task\("),
            "base=QueueOnce": re.compile(r"base=QueueOnce"),
        }
        allowed = {BACKEND / "app" / "queues.py"}
        found = []
        for path in _source_files():
            if path in allowed:
                continue
            text = path.read_text()
            for label, pattern in forbidden.items():
                if pattern.search(text):
                    found.append(f"{path.relative_to(BACKEND)}: {label}")
        self.assertEqual(found, [])


class QueueBaseClassTestCase(SimpleTestCase):
    def test_every_task_is_an_app_task(self):
        others = sorted(
            name
            for name, task in _tasks().items()
            if not isinstance(task, AppTask)
            and not name.startswith(THIRD_PARTY_BASES)
        )
        self.assertEqual(others, [])

    def test_third_party_exceptions_still_dedupe(self):
        for name, task in _tasks().items():
            if name.startswith(THIRD_PARTY_BASES) and not isinstance(
                task, AppTask
            ):
                with self.subTest(name):
                    self.assertIsInstance(task, QueueOnce)


class QueueWorkersTestCase(SimpleTestCase):
    @skipUnless(COMPOSE_PROD.exists(), "compose file is outside the image")
    def test_production_runs_a_worker_for_every_queue(self):
        consumed = _consumed_queues(COMPOSE_PROD.read_text())
        self.assertEqual(sorted(set(QUEUES) - consumed), [])
        self.assertEqual(sorted(consumed - set(QUEUES)), [], "stale queue")

    @skipUnless(DEV_SH.exists(), "dev.sh is outside the image")
    def test_dev_worker_consumes_every_queue(self):
        self.assertEqual(
            sorted(set(QUEUES) - _consumed_queues(DEV_SH.read_text())), []
        )

    def test_declared_queues_match_the_registry(self):
        declared = [queue.name for queue in app.conf.task_queues]
        self.assertEqual(sorted(declared), sorted(QUEUES))
        self.assertEqual(app.conf.task_default_queue, FAST_LANE)


class QueueMonitoringTestCase(SimpleTestCase):
    def test_cron_monitors_name_real_schedules(self):
        missing = sorted(
            set(CRON_MONITORED_SCHEDULES) - set(settings.CELERYBEAT_SCHEDULE)
        )
        self.assertEqual(missing, [])

    def test_queue_limits_are_sane(self):
        for spec in QUEUES.values():
            with self.subTest(spec.name):
                self.assertGreater(spec.max_wait_seconds, 0)
                self.assertGreater(spec.dedupe_ttl_seconds, 0)
                self.assertTrue(spec.purpose)
