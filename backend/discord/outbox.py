"""
Send Discord DMs and channel posts from Celery instead of the web request.

DiscordClient retries rate limits with backoff, so a slow or rate-limited
Discord can hold a web worker for minutes. Request handlers (and signals that
fire inside them) build the message as before and queue it here; a worker
sends it once the database transaction commits.

These are transport tasks: what is sent and to whom is decided by the caller.
Person-directed messages that members should be able to mute belong in the
notifications app (`notifications.service.notify_user`) instead; see
docs/notifications/README.md.
"""

from __future__ import annotations

import logging

from django.db import transaction

from app.celery import app
from discord.client import DiscordClient

logger = logging.getLogger(__name__)


@app.task(ignore_result=True)
def send_discord_dm_task(
    discord_user_id: str,
    messages: list[str] | None = None,
    payload: dict | None = None,
    context: str = "",
) -> bool:
    """DM a Discord user: `payload` first (if any), then each message in order.

    Failures are logged and dropped, as they were when sent inline. Discord
    rate limits are already retried inside DiscordClient.
    """
    client = DiscordClient()
    try:
        if payload is not None:
            client.send_dm(str(discord_user_id), payload=payload)
        for message in messages or []:
            client.send_dm(str(discord_user_id), message=message)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning(
            "Failed to send Discord DM to %s (%s)",
            discord_user_id,
            context or "no context",
            exc_info=True,
        )
        return False
    return True


@app.task(ignore_result=True)
def post_discord_message_task(
    channel_id: int | str,
    message: str | None = None,
    payload: dict | None = None,
    context: str = "",
) -> bool:
    """Post one message to a Discord channel. Failures are logged and dropped."""
    try:
        if payload is not None:
            DiscordClient().create_message(
                channel_id=channel_id, payload=payload
            )
        else:
            DiscordClient().create_message(
                channel_id=channel_id, message=message
            )
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning(
            "Failed to post Discord message to channel %s (%s)",
            channel_id,
            context or "no context",
            exc_info=True,
        )
        return False
    return True


def queue_dm(
    discord_user_id: int | str,
    *,
    message: str | None = None,
    messages: list[str] | None = None,
    payload: dict | None = None,
    context: str = "",
) -> None:
    """Send a DM from a worker after the current transaction commits.

    Several messages go to one task so they arrive in order.
    """
    if messages is None:
        messages = [] if message is None else [message]
    if not messages and payload is None:
        raise ValueError("queue_dm needs a message or a payload")
    args = (str(discord_user_id), list(messages), payload, context)
    on_commit_enqueue(send_discord_dm_task, args, context)


def queue_channel_message(
    channel_id: int | str,
    *,
    message: str | None = None,
    payload: dict | None = None,
    context: str = "",
) -> None:
    """Post to a channel from a worker after the current transaction commits."""
    if message is None and payload is None:
        raise ValueError("queue_channel_message needs a message or a payload")
    args = (channel_id, message, payload, context)
    on_commit_enqueue(post_discord_message_task, args, context)


def on_commit_enqueue(task, args: tuple = (), context: str = "", **options):
    """Enqueue `task` once the current transaction commits.

    A broker outage must not fail the request that triggered the message
    (the inline sends it replaces were best-effort too), so enqueue errors
    are logged, not raised.
    """

    def _enqueue():
        try:
            task.apply_async(args=args, **options)
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception(
                "Could not queue %s (%s)", task.name, context or "no context"
            )

    transaction.on_commit(_enqueue)
