#!/usr/bin/env python3
"""List the newest uploads on the alliance YouTube channels.

Reads each channel's public feed (the newest 15 uploads, with date, view
count and description). No API key and no login. The agent reads the titles
and descriptions and picks the video that fits each recruitment post; this
script does not rank or match anything.
"""

from __future__ import annotations

import argparse
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scout_lib import (  # noqa: E402
    add_base_args,
    cutoff_from_days,
    emit,
    load_config_from_args,
)

FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}
# Some uploads open their description with the CCP trademark notice. It says
# nothing about the video, so it is cut before the description is trimmed.
LEGAL_OPENER = "EVE Online, the EVE logo"
DESCRIPTION_CHARS = 600


def _description(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith(LEGAL_OPENER):
        return ""
    text = " ".join(line.strip() for line in text.splitlines() if line.strip())
    if len(text) > DESCRIPTION_CHARS:
        text = text[:DESCRIPTION_CHARS].rsplit(" ", 1)[0] + " …"
    return text


def _is_short(video_id: str, user_agent: str) -> bool | None:
    """True for a Short, False for a normal upload, None when YouTube won't say.

    youtube.com/shorts/<id> answers 200 for a Short and redirects a normal
    upload to its watch page.
    """
    try:
        resp = requests.head(
            f"https://www.youtube.com/shorts/{video_id}",
            headers={"User-Agent": user_agent},
            allow_redirects=False,
            timeout=10,
        )
    except requests.RequestException:
        return None
    if resp.status_code == 200:
        return True
    if resp.status_code == 303:
        return False
    return None


def fetch_channel(channel: dict, cutoff: datetime | None, user_agent: str) -> list[dict]:
    resp = requests.get(
        FEED_URL.format(channel_id=channel["channel_id"]),
        headers={"User-Agent": user_agent},
        timeout=15,
    )
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    now = datetime.now(timezone.utc)

    videos: list[dict] = []
    for entry in root.findall("atom:entry", NS):
        video_id = entry.findtext("yt:videoId", namespaces=NS)
        published_raw = entry.findtext("atom:published", namespaces=NS)
        if not video_id or not published_raw:
            continue
        published = datetime.fromisoformat(published_raw)
        if cutoff and published < cutoff:
            continue
        group = entry.find("media:group", NS)
        stats = entry.find("media:group/media:community/media:statistics", NS)
        videos.append(
            {
                "channel": channel.get("handle") or channel["channel_id"],
                "title": entry.findtext("atom:title", namespaces=NS) or "",
                "url": f"https://youtu.be/{video_id}",
                "video_id": video_id,
                "published": published.date().isoformat(),
                "age_days": (now - published).days,
                "views": int(stats.get("views", 0)) if stats is not None else None,
                "description": _description(
                    group.findtext("media:description", namespaces=NS)
                    if group is not None
                    else ""
                ),
            }
        )
    return videos


def main() -> None:
    parser = argparse.ArgumentParser(
        description="List the newest uploads on the alliance YouTube channels"
    )
    add_base_args(parser)
    parser.add_argument(
        "--days",
        type=int,
        default=180,
        help="Lookback window; 0 lists everything in the feed (default: 180)",
    )
    parser.add_argument(
        "--skip-shorts-check",
        action="store_true",
        help="Do not ask YouTube which uploads are Shorts",
    )
    args = parser.parse_args()
    config = load_config_from_args(args)

    channels = config.get("youtube", {}).get("channels") or []
    cutoff = cutoff_from_days(args.days) if args.days > 0 else None

    videos: list[dict] = []
    errors: list[dict] = []
    for channel in channels:
        handle = channel.get("handle") or channel.get("channel_id")
        try:
            videos.extend(fetch_channel(channel, cutoff, args.user_agent))
        except (requests.RequestException, ET.ParseError, KeyError) as exc:
            errors.append({"channel": handle, "error": str(exc)})
        time.sleep(0.2)

    videos.sort(key=lambda v: v["published"], reverse=True)
    for video in videos:
        video["short"] = (
            None
            if args.skip_shorts_check
            else _is_short(video["video_id"], args.user_agent)
        )

    names = ", ".join("@" + (c.get("handle") or c["channel_id"]) for c in channels)
    since = f" since {cutoff.date().isoformat()}" if cutoff else ""
    summary = f"videos: {len(videos)} from {names or 'no channels in config'}{since}"
    if errors:
        summary += f" ({len(errors)} channel feed failed; browse it by hand)"

    payload = {
        "script": "fetch_videos",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "channels": [
            {
                "handle": c.get("handle"),
                "url": f"https://www.youtube.com/@{c['handle']}/videos"
                if c.get("handle")
                else f"https://www.youtube.com/channel/{c['channel_id']}/videos",
            }
            for c in channels
        ],
        "cutoff": cutoff.date().isoformat() if cutoff else None,
        "days": args.days,
        "videos": videos,
        "errors": errors,
        "summary": summary,
    }
    emit(payload, args.json)


if __name__ == "__main__":
    main()
