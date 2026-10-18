"""Announce a tribe group's post in the group's Discord channel, once."""

from __future__ import annotations

import logging

from django.utils import timezone

from app.links import site_url
from discord.outbox import queue_channel_message

from .models import EvePost

logger = logging.getLogger(__name__)


def post_url(post: EvePost) -> str:
    return site_url(f"/alliance/propaganda/{post.slug}-{post.id}")


def group_post_announcement(post: EvePost) -> str:
    """Role mention, the title and the link (one message)."""
    # pylint: disable=import-outside-toplevel
    from tribes.helpers.publishing import group_role_mention

    group = post.host_group
    mention = group_role_mention(group)
    prefix = f"{mention} " if mention else ""
    return f"{prefix}New post from {group.name}: **{post.title}**\n" + (
        post_url(post)
    )


def announce_group_post(post: EvePost) -> bool:
    """Queue the announcement the first time a group post is published.

    Returns True when one was queued. A draft, an alliance post, a group
    with no channel or a post already announced sends nothing.
    """
    if not post.host_group_id or post.state != "published":
        return False
    if post.announced_at is not None:
        return False
    channel_id = post.host_group.effective_discord_channel_id
    if not channel_id:
        return False
    now = timezone.now()
    # Claim the announcement so two saves can't both send it.
    claimed = EvePost.objects.filter(
        pk=post.pk, announced_at__isnull=True
    ).update(announced_at=now)
    if not claimed:
        return False
    post.announced_at = now
    queue_channel_message(
        channel_id,
        message=group_post_announcement(post),
        context=f"post {post.id} announcement",
    )
    return True
