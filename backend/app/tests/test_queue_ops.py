from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from app.queue_health import PRIORITY_SEPARATOR
from app.queue_ops import (
    clear_queued_locks,
    dedupable_task_names,
    dedupe_queued_messages,
)
from app.queues import QUEUES


class DedupeQueuedMessagesTestCase(SimpleTestCase):
    def test_skips_the_fast_lane_and_opted_out_tasks(self):
        registry = {
            "market.tasks.a": SimpleNamespace(dedupe=True),
            "market.tasks.b": SimpleNamespace(dedupe=False),
            "discord.outbox.post_discord_message_task": SimpleNamespace(
                dedupe=True
            ),
            "eveuniverse.tasks.load_map": SimpleNamespace(),
        }
        self.assertEqual(dedupable_task_names(registry), ["market.tasks.a"])

    def test_passes_every_priority_list_in_drain_order(self):
        client = MagicMock()
        client.eval.return_value = [b"market.tasks.a", 4]
        removed = dedupe_queued_messages(client, ["market.tasks.a"], False)
        self.assertEqual(removed, {"market.tasks.a": 4})
        args = client.eval.call_args.args
        key_count = args[1]
        keys = args[2 : 2 + key_count]
        self.assertEqual(key_count, len(QUEUES) * 10)
        self.assertEqual(keys[0], "celery")
        self.assertEqual(keys[5], f"celery{PRIORITY_SEPARATOR}5")
        self.assertEqual(args[2 + key_count], "1")  # dry run
        self.assertEqual(list(args[3 + key_count :]), ["market.tasks.a"])


class ClearQueuedLocksTestCase(SimpleTestCase):
    def test_needs_a_pattern_capable_cache(self):
        with self.assertRaises(RuntimeError):
            clear_queued_locks()

    def test_deletes_by_pattern(self):
        fake = MagicMock()
        fake.delete_pattern.return_value = 7
        with patch("app.queue_ops.cache", fake):
            self.assertEqual(clear_queued_locks("market.tasks.a"), 7)
        fake.delete_pattern.assert_called_once_with(
            "task-queued:market.tasks.a:*"
        )


class CeleryQueuesCommandTestCase(SimpleTestCase):
    @patch("app.management.commands.celery_queues.broker_client")
    def test_status(self, broker_client):
        client = MagicMock()
        client.llen.return_value = 0
        broker_client.return_value = client
        out = StringIO()
        call_command("celery_queues", "status", stdout=out)
        self.assertIn("celery", out.getvalue())
        self.assertIn("community", out.getvalue())

    @patch("app.management.commands.celery_queues.dedupe_queued_messages")
    @patch("app.management.commands.celery_queues.broker_client")
    def test_dedupe_is_a_dry_run_by_default(self, broker_client, dedupe):
        broker_client.return_value = MagicMock(llen=MagicMock(return_value=0))
        dedupe.return_value = {"market.tasks.a": 3}
        out = StringIO()
        call_command("celery_queues", "dedupe", stdout=out)
        self.assertFalse(dedupe.call_args.args[2])
        self.assertIn("Would remove", out.getvalue())
        call_command("celery_queues", "dedupe", "--apply", stdout=out)
        self.assertTrue(dedupe.call_args.args[2])

    def test_clear_locks_reports_an_unsupported_cache(self):
        with self.assertRaises(CommandError):
            call_command("celery_queues", "clear-locks")
