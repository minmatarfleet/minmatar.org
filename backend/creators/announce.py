"""Share a creator account's new media in its Discord channel.

Set `CreatorAccount.discord_channel_id` (Django admin) and each new video,
VOD or Reddit post the media sync picks up is posted there once.
"""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from creators.models import (
    CreatorAccount,
    CreatorAccountStatus,
    CreatorItem,
    CreatorItemKind,
)
from discord.outbox import queue_channel_message

# Only media this recent is posted, so setting a channel on an account
# doesn't post its back catalogue.
MAX_AGE = timedelta(days=2)

KIND_LABELS = {
    CreatorItemKind.VIDEO: "video",
    CreatorItemKind.VOD: "VOD",
    CreatorItemKind.STREAM: "stream",
    CreatorItemKind.REDDIT_POST: "Reddit post",
}


def announcement_message(account: CreatorAccount, item: CreatorItem) -> str:
    name = account.platform_username or account.user.username
    kind = KIND_LABELS.get(item.kind, "post")
    title = item.title or "Untitled"
    # Discord unfurls the link (the YouTube / Twitch player, the Reddit post).
    return f"New {kind} from {name}: **{title}**\n{item.url}"


def announce_new_items(account: CreatorAccount) -> list[int]:
    """Post the account's recent, not yet posted items. Safe to run twice.

    Returns the ids of the items posted.
    """
    channel_id = (account.discord_channel_id or "").strip()
    if not channel_id or account.status != CreatorAccountStatus.APPROVED:
        return []
    now = timezone.now()
    since = now - MAX_AGE
    if account.import_start_at and account.import_start_at > since:
        since = account.import_start_at
    items = (
        CreatorItem.objects.filter(
            account=account,
            announced_at__isnull=True,
            hidden=False,
            published_at__gte=since,
        )
        .exclude(Q(url="") | Q(url__isnull=True))
        .order_by("published_at", "id")
    )
    posted = []
    for item in items:
        # Claim the item first so two overlapping syncs can't both post it.
        claimed = CreatorItem.objects.filter(
            pk=item.pk, announced_at__isnull=True
        ).update(announced_at=now)
        if not claimed:
            continue
        queue_channel_message(
            channel_id,
            message=announcement_message(account, item),
            context=f"creator item {item.id} announcement",
        )
        posted.append(item.id)
    return posted
