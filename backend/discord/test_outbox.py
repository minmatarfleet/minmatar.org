"""Tests for queued Discord DMs and channel posts."""

from unittest.mock import patch

from django.test import TestCase

from discord.outbox import (
    post_discord_message_task,
    queue_channel_message,
    queue_dm,
    send_discord_dm_task,
)


@patch("discord.outbox.DiscordClient")
class DiscordOutboxTaskTestCase(TestCase):
    def test_dm_task_sends_messages_in_order(self, client_cls):
        self.assertTrue(send_discord_dm_task("123", ["first", "second"]))
        calls = client_cls.return_value.send_dm.call_args_list
        self.assertEqual([("123",), ("123",)], [call.args for call in calls])
        self.assertEqual(
            ["first", "second"], [call.kwargs["message"] for call in calls]
        )

    def test_dm_task_sends_payload(self, client_cls):
        payload = {"embeds": [{"title": "x"}]}
        self.assertTrue(send_discord_dm_task("123", [], payload))
        client_cls.return_value.send_dm.assert_called_once_with(
            "123", payload=payload
        )

    def test_dm_task_logs_and_drops_failures(self, client_cls):
        client_cls.return_value.send_dm.side_effect = RuntimeError("closed")
        with self.assertLogs("discord.outbox", "WARNING") as logs:
            self.assertFalse(
                send_discord_dm_task("123", ["hi"], None, "cyno DM")
            )
        self.assertIn("cyno DM", logs.output[0])

    def test_channel_task_posts_message_or_payload(self, client_cls):
        self.assertTrue(post_discord_message_task(42, "hello"))
        client_cls.return_value.create_message.assert_called_with(
            channel_id=42, message="hello"
        )
        self.assertTrue(post_discord_message_task(42, None, {"content": "x"}))
        client_cls.return_value.create_message.assert_called_with(
            channel_id=42, payload={"content": "x"}
        )

    def test_channel_task_logs_and_drops_failures(self, client_cls):
        client_cls.return_value.create_message.side_effect = RuntimeError()
        with self.assertLogs("discord.outbox", "WARNING"):
            self.assertFalse(post_discord_message_task(42, "hello"))


class DiscordOutboxQueueTestCase(TestCase):
    @patch("discord.outbox.send_discord_dm_task")
    @patch("discord.outbox.DiscordClient")
    def test_queue_dm_waits_for_commit(self, client_cls, task):
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            queue_dm(123, message="hi", context="test")
        task.apply_async.assert_not_called()
        self.assertEqual(1, len(callbacks))
        callbacks[0]()
        task.apply_async.assert_called_once_with(
            args=("123", ["hi"], None, "test")
        )
        client_cls.assert_not_called()

    @patch("discord.outbox.post_discord_message_task")
    def test_queue_channel_message_waits_for_commit(self, task):
        with self.captureOnCommitCallbacks(execute=True):
            queue_channel_message(42, payload={"content": "x"})
        task.apply_async.assert_called_once_with(
            args=(42, None, {"content": "x"}, "")
        )

    @patch("discord.outbox.send_discord_dm_task")
    def test_broker_errors_do_not_fail_the_caller(self, task):
        task.name = "send_discord_dm_task"
        task.apply_async.side_effect = ConnectionError("broker down")
        with self.assertLogs("discord.outbox", "ERROR"):
            with self.captureOnCommitCallbacks(execute=True):
                queue_dm(123, message="hi")

    def test_queue_dm_needs_content(self):
        with self.assertRaises(ValueError):
            queue_dm(123)
        with self.assertRaises(ValueError):
            queue_channel_message(42)
