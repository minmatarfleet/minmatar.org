"""
Mirror an order into a Discord forum thread.

Hangar buyback purchase orders and LP buyback market orders each get a forum
thread in the channel flagged for them (DiscordChannel.receive_*). Both flows
use one ForumThreadMirror for the plumbing (channel lookup, tag choice,
create, post, archive); the messages themselves stay in each feature.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from discord.client import DiscordClient
from discord.models import DiscordChannel

logger = logging.getLogger(__name__)

# Post, let message traffic settle, then archive: a post that lands after the
# archive makes Discord reopen the thread.
THREAD_ARCHIVE_DELAY_SECONDS = 5


def flagged_channel_row(flag: str) -> tuple[int, int] | None:
    """(channel_id, guild_id) of the active channel with this receive_* flag."""
    row = (
        DiscordChannel.objects.filter(**{flag: True}, guild__is_active=True)
        .values_list("channel_id", "guild__guild_id")
        .first()
    )
    if not row or not row[0]:
        return None
    return int(row[0]), int(row[1])


@dataclass(frozen=True)
class ForumThreadMirror:
    """Forum-thread plumbing for one kind of order.

    client: returns the DiscordClient to use, looked up per call so feature
        modules (and their tests) keep their own module-level client.
    close_task: returns the Celery task that archives a thread by id; used to
        archive after THREAD_ARCHIVE_DELAY_SECONDS without holding a worker.
    """

    label: str
    channel_flag: str
    preferred_tags: frozenset[str]
    client: Callable[[], DiscordClient]
    close_task: Callable[[], Any]

    def channel_row(self) -> tuple[int, int] | None:
        """(channel_id, guild_id) of the active channel with our flag."""
        return flagged_channel_row(self.channel_flag)

    def channel_id(self) -> int | None:
        row = self.channel_row()
        return row[0] if row else None

    def default_tag_ids(self, channel_id: int) -> list[str]:
        """The first preferred forum tag, else the first tag, else none.

        Forums with REQUIRE_TAG reject threads without one.
        """
        try:
            channel = self.client().get_channel(channel_id).json()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning(
                "Could not fetch %s forum channel %s for tags: %s",
                self.label,
                channel_id,
                exc,
            )
            return []

        tags = channel.get("available_tags") or []
        if not tags:
            return []
        for tag in tags:
            name = str(tag.get("name") or "").strip().lower()
            if name in self.preferred_tags:
                return [str(tag["id"])]
        return [str(tags[0]["id"])]

    def create_thread(
        self,
        title: str,
        message: str,
        components: list[dict] | None = None,
    ) -> int | None:
        """Create the order's thread; its id, or None (logged) on failure."""
        channel_id = self.channel_id()
        if not channel_id:
            logger.warning(
                "No DiscordChannel with %s; skip thread", self.channel_flag
            )
            return None
        kwargs: dict[str, Any] = {
            "channel_id": channel_id,
            "title": title[:100],
            "message": message,
            "applied_tags": self.default_tag_ids(channel_id),
        }
        if components:
            kwargs["components"] = components
        try:
            response = self.client().create_forum_thread(**kwargs)
            return int(response.json()["id"])
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error(
                "Failed creating %s Discord thread (channel=%s): %s",
                self.label,
                channel_id,
                exc,
            )
            return None

    def post(
        self,
        thread_id: int | None,
        message: str,
        components: list[dict] | None = None,
    ) -> bool:
        """Post in a thread; False when there is no thread or it failed."""
        if not thread_id:
            return False
        payload: dict[str, Any] = {"content": message}
        if components:
            payload["components"] = components
        try:
            self.client().create_message(channel_id=thread_id, payload=payload)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error(
                "Failed posting %s Discord update: %s", self.label, exc
            )
            return False
        return True

    def close(self, thread_id: int | None) -> bool:
        """Archive and lock a thread now; False when none or it failed."""
        if not thread_id:
            return False
        try:
            self.client().close_thread(channel_id=int(thread_id))
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error(
                "Failed closing %s Discord thread %s: %s",
                self.label,
                thread_id,
                exc,
            )
            return False
        return True

    def post_then_close(self, thread_id: int | None, message: str) -> None:
        """Post a final notice, then archive the thread a few seconds later.

        The archive runs as a Celery task with a countdown instead of a
        sleep, so the worker is free while Discord settles.
        """
        if not thread_id:
            return
        self.post(thread_id, message)
        self.close_task().apply_async(
            args=[int(thread_id)], countdown=THREAD_ARCHIVE_DELAY_SECONDS
        )
