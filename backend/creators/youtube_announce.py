"""Share new uploads from the alliance YouTube channel in Discord.

Polls the channel's public RSS feed (no API key; it lists both videos and
Shorts, and links Shorts as /shorts/<id>) and posts each new upload once to
`settings.DISCORD_YOUTUBE_ANNOUNCE_CHANNEL_ID` (#propaganda).
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta

import requests
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from creators.models import YouTubeAnnouncement
from creators.post_import import ATOM_NS, YT_NS, _parse_ts
from discord.outbox import queue_channel_message

logger = logging.getLogger(__name__)

FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
# An upload older than this when first seen is recorded, not posted: a
# re-published or late-appearing old video shouldn't ping the channel.
MAX_AGE = timedelta(days=2)


@dataclass(frozen=True)
class FeedVideo:
    video_id: str
    title: str
    url: str
    is_short: bool
    published_at: datetime | None


def fetch_feed(channel_id: str) -> list[FeedVideo] | None:
    """The feed's uploads, newest first; None when the feed can't be read."""
    try:
        response = requests.get(
            FEED_URL.format(channel_id=channel_id), timeout=20
        )
    except requests.RequestException:
        logger.warning("YouTube feed request failed for %s", channel_id)
        return None
    if response.status_code >= 400:
        logger.warning(
            "YouTube feed failed for %s: %s", channel_id, response.status_code
        )
        return None
    try:
        return parse_feed(response.content)
    except ET.ParseError:
        logger.warning("YouTube feed for %s is not valid XML", channel_id)
        return None


def parse_feed(content: bytes) -> list[FeedVideo]:
    root = ET.fromstring(content)
    videos = []
    for entry in root.findall(f"{ATOM_NS}entry"):
        video_el = entry.find(f"{YT_NS}videoId")
        video_id = (
            (video_el.text or "").strip() if video_el is not None else ""
        )
        if not video_id:
            continue
        title_el = entry.find(f"{ATOM_NS}title")
        published_el = entry.find(f"{ATOM_NS}published")
        link_el = entry.find(f"{ATOM_NS}link[@rel='alternate']")
        link = link_el.get("href", "") if link_el is not None else ""
        is_short = "/shorts/" in link
        url = (
            f"https://www.youtube.com/shorts/{video_id}"
            if is_short
            else f"https://www.youtube.com/watch?v={video_id}"
        )
        videos.append(
            FeedVideo(
                video_id=video_id,
                title=(
                    (title_el.text or "").strip()
                    if title_el is not None
                    else ""
                ),
                url=url,
                is_short=is_short,
                published_at=_parse_ts(
                    published_el.text if published_el is not None else None
                ),
            )
        )
    return videos


def announcement_message(video: FeedVideo) -> str:
    kind = "short" if video.is_short else "video"
    title = video.title or "Untitled"
    # Discord unfurls the link into the YouTube player.
    return f"New {kind} from Minmatar Fleet: **{title}**\n{video.url}"


def announce_new_uploads() -> dict:
    """Post each upload not seen before. Safe to run twice."""
    channel_id = settings.YOUTUBE_ANNOUNCE_CHANNEL_ID
    discord_channel_id = settings.DISCORD_YOUTUBE_ANNOUNCE_CHANNEL_ID
    if not channel_id or not discord_channel_id:
        return {"status": "disabled"}
    videos = fetch_feed(channel_id)
    if videos is None:
        return {"status": "feed_unavailable"}

    first_poll = not YouTubeAnnouncement.objects.filter(
        youtube_channel_id=channel_id
    ).exists()
    seen = set(
        YouTubeAnnouncement.objects.filter(
            video_id__in=[v.video_id for v in videos]
        ).values_list("video_id", flat=True)
    )
    now = timezone.now()
    announced, recorded = [], []
    # Oldest first, so several new uploads post in the order they went up.
    for video in reversed(videos):
        if video.video_id in seen:
            continue
        too_old = video.published_at is None or (
            now - video.published_at > MAX_AGE
        )
        post = not first_poll and not too_old
        try:
            with transaction.atomic():
                YouTubeAnnouncement.objects.create(
                    youtube_channel_id=channel_id,
                    video_id=video.video_id,
                    title=video.title[:512],
                    url=video.url,
                    is_short=video.is_short,
                    published_at=video.published_at,
                    announced_at=now if post else None,
                )
                if post:
                    queue_channel_message(
                        discord_channel_id,
                        message=announcement_message(video),
                        context=f"youtube {video.video_id} announcement",
                    )
        except IntegrityError:
            # Another run recorded it first; it sends the post.
            continue
        (announced if post else recorded).append(video.video_id)
    return {
        "status": "ok",
        "first_poll": first_poll,
        "announced": announced,
        "recorded": recorded,
    }
