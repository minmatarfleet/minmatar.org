import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import SimpleTestCase

from app.queue_health import (
    PRIORITY_SEPARATOR,
    QueueStatus,
    measure_queues,
    message_wait,
    report_queues,
)
from app.tasks import monitor_queue_health

NOW = 1_800_000_000.0


def _message(task, enqueued=None, sentry=None, eta=None):
    headers = {"task": task, "eta": eta}
    if enqueued is not None:
        headers["enqueued_at"] = enqueued
    if sentry is not None:
        headers["sentry-task-enqueued-time"] = sentry
    return json.dumps({"headers": headers}).encode()


class FakeRedis:
    """llen/lrange over kombu-style lists (newest on the left)."""

    def __init__(self, lists):
        self.lists = lists

    def llen(self, key):
        return len(self.lists.get(key, []))

    def lrange(self, key, start, end):
        items = self.lists.get(key, [])
        start = max(len(items) + start, 0) if start < 0 else start
        end = len(items) + end if end < 0 else end
        return items[start : end + 1]

    def hlen(self, key):
        return 3


class MessageWaitTestCase(SimpleTestCase):
    def test_reads_our_header_then_sentrys(self):
        self.assertEqual(message_wait(_message("t", NOW - 30), NOW), 30)
        self.assertEqual(message_wait(_message("t", sentry=NOW - 45), NOW), 45)

    def test_a_countdown_counts_from_its_eta(self):
        eta = datetime.fromtimestamp(NOW - 10, timezone.utc).isoformat()
        self.assertEqual(
            message_wait(_message("t", NOW - 300, eta=eta), NOW), 10
        )
        future = datetime.fromtimestamp(NOW + 60, timezone.utc).isoformat()
        self.assertEqual(
            message_wait(_message("t", NOW - 300, eta=future), NOW), 0
        )

    def test_unknown_when_no_timestamp_or_garbage(self):
        self.assertIsNone(message_wait(_message("t"), NOW))
        self.assertIsNone(message_wait(b"not json", NOW))


class MeasureQueuesTestCase(SimpleTestCase):
    def test_depth_and_oldest_wait_across_priority_lists(self):
        client = FakeRedis(
            {
                f"eveonline{PRIORITY_SEPARATOR}5": [
                    _message("structures.a", NOW - 5),
                    _message("structures.a", NOW - 900),
                ],
                "eveonline": [_message("eveonline.b", NOW - 60)],
            }
        )
        report = measure_queues(client, NOW)
        status = report["eveonline"]
        self.assertEqual(status.depth, 3)
        self.assertEqual(status.oldest_wait, 900)
        self.assertEqual(
            status.oldest_tasks, {"structures.a": 2, "eveonline.b": 1}
        )
        self.assertEqual(report["market"].depth, 0)
        self.assertIsNone(report["market"].oldest_wait)


class ReportQueuesTestCase(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @patch("app.queue_health.sentry_sdk.capture_message")
    @patch("app.queue_health.monitoring.gauge")
    def test_gauges_every_queue_and_warns_once_per_backlog(
        self, gauge, capture
    ):
        report = {
            "celery": QueueStatus("celery", depth=2, oldest_wait=5),
            "market": QueueStatus("market", depth=900, oldest_wait=4000),
        }
        report_queues(report, unacked=3)
        report_queues(report, unacked=3)

        depths = {
            call.kwargs["queue"]: call.args[1]
            for call in gauge.call_args_list
            if call.args[0] == "celery.queue.depth"
        }
        self.assertEqual(depths, {"celery": 2, "market": 900})
        gauge.assert_any_call("celery.queue.reserved", 3)
        capture.assert_called_once_with(
            "Celery queue market is backed up", level="warning"
        )


class MonitorQueueHealthTaskTestCase(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @patch("app.queue_health.monitoring.gauge")
    @patch("app.tasks.broker_client")
    def test_returns_a_summary(self, broker_client, gauge_mock):
        broker_client.return_value = FakeRedis(
            {"feed": [_message("feed.tasks.poll_zkill_r2z2", NOW - 1)]}
        )
        with patch("app.queue_health.time.time", return_value=NOW):
            summary = monitor_queue_health()
        self.assertEqual(summary["feed"]["depth"], 1)
        self.assertEqual(summary["feed"]["oldest_wait"], 1)

    @patch("app.queue_health.monitoring.gauge")
    @patch("app.tasks.broker_client")
    def test_survives_a_broker_without_unacked(self, broker_client, gauge):
        client = MagicMock()
        client.llen.return_value = 0
        client.hlen.side_effect = ConnectionError
        broker_client.return_value = client
        monitor_queue_health()
        self.assertNotIn(
            "celery.queue.reserved",
            [call.args[0] for call in gauge.call_args_list],
        )
