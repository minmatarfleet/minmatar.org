"""Tests for the shared order forum-thread plumbing."""

from unittest.mock import MagicMock

from django.test import TestCase

from discord.forum_threads import (
    THREAD_ARCHIVE_DELAY_SECONDS,
    ForumThreadMirror,
)
from discord.models import DiscordChannel, DiscordGuild


class ForumThreadMirrorTestCase(TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.close_task = MagicMock()
        self.mirror = ForumThreadMirror(
            label="test orders",
            channel_flag="receive_buyback",
            preferred_tags=frozenset({"open"}),
            client=lambda: self.client,
            close_task=lambda: self.close_task,
        )
        guild = DiscordGuild.objects.create(
            guild_id=42, name="Guild", is_active=True
        )
        DiscordChannel.objects.update_or_create(
            channel_id=7001,
            defaults={
                "guild": guild,
                "name": "orders",
                "channel_type": DiscordChannel.FORUM,
                "receive_buyback": True,
            },
        )

    def test_channel_row_needs_an_active_guild(self):
        self.assertEqual((7001, 42), self.mirror.channel_row())
        DiscordGuild.objects.filter(guild_id=42).update(is_active=False)
        self.assertIsNone(self.mirror.channel_id())

    def test_create_failure_is_logged_not_raised(self):
        self.client.get_channel.side_effect = RuntimeError("no tags")
        self.client.create_forum_thread.side_effect = RuntimeError("down")
        with self.assertLogs("discord.forum_threads", "WARNING") as logs:
            self.assertIsNone(self.mirror.create_thread("t", "m"))
        self.assertTrue(any("test orders" in line for line in logs.output))

    def test_post_and_close_without_thread_do_nothing(self):
        self.assertFalse(self.mirror.post(None, "hi"))
        self.assertFalse(self.mirror.close(None))
        self.mirror.post_then_close(None, "bye")
        self.client.create_message.assert_not_called()
        self.close_task.apply_async.assert_not_called()

    def test_post_then_close_schedules_the_archive(self):
        self.mirror.post_then_close(9001, "bye")
        self.client.create_message.assert_called_once_with(
            channel_id=9001, payload={"content": "bye"}
        )
        self.client.close_thread.assert_not_called()
        self.close_task.apply_async.assert_called_once_with(
            args=[9001], countdown=THREAD_ARCHIVE_DELAY_SECONDS
        )

    def test_failed_post_or_close_returns_false(self):
        self.client.create_message.side_effect = RuntimeError("down")
        self.client.close_thread.side_effect = RuntimeError("down")
        with self.assertLogs("discord.forum_threads", "ERROR"):
            self.assertFalse(self.mirror.post(9001, "hi"))
            self.assertFalse(self.mirror.close(9001))
