"""EVE Online forums (Discourse) thread links."""

import logging
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

import requests

logger = logging.getLogger(__name__)

FORUMS_HOST = "forums.eveonline.com"
# Corporations & Alliances > Recruitment Center, from
# https://forums.eveonline.com/categories.json. Topic JSON only carries the
# topic's own category id, so any future Recruitment Center subcategory
# needs adding here (it has none today).
RECRUITMENT_CENTER_CATEGORY_ID = 63
RECRUITMENT_CENTER_CATEGORY_IDS = frozenset({RECRUITMENT_CENTER_CATEGORY_ID})
FETCH_TIMEOUT_SECONDS = 5
USER_AGENT = "minmatar.org recruitment"

# /t/<slug>/<topic_id>, optionally followed by /<post_number>.
_TOPIC_PATH = re.compile(r"^/t/([^/]+)/(\d+)(?:/\d+)?/?$")


class ForumUrlError(ValueError):
    """Not a forums.eveonline.com thread. `code` names the problem."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class TopicNotFound(Exception):
    """The forum answered, and has no such (public) topic."""


@dataclass(frozen=True)
class ForumTopicUrl:
    url: str
    slug: str
    topic_id: int


def topic_url(slug: str, topic_id: int) -> str:
    return f"https://{FORUMS_HOST}/t/{slug}/{topic_id}"


def parse_topic_url(value: str) -> ForumTopicUrl:
    """The canonical thread URL for a link to a thread or one of its posts.

    Accepts https://forums.eveonline.com/t/<slug>/<topic_id> with an
    optional /<post_number>, query string or fragment.
    """
    value = (value or "").strip()
    if not value:
        raise ForumUrlError("url_required")
    try:
        parts = urlsplit(value)
        host = (parts.hostname or "").lower()
    except ValueError as e:
        raise ForumUrlError("invalid_url") from e
    if parts.scheme not in ("http", "https") or not host:
        raise ForumUrlError("invalid_url")
    if host != FORUMS_HOST or parts.port not in (None, 443):
        raise ForumUrlError("not_eve_forums")
    match = _TOPIC_PATH.match(parts.path)
    if not match:
        raise ForumUrlError("not_a_thread")
    slug, topic_id = match.group(1), int(match.group(2))
    if topic_id <= 0:
        raise ForumUrlError("not_a_thread")
    return ForumTopicUrl(topic_url(slug, topic_id), slug, topic_id)


def fetch_topic(topic_id: int) -> dict | None:
    """The topic's Discourse JSON, or None if the forum couldn't be reached.

    Raises TopicNotFound when the forum says the topic doesn't exist.
    """
    endpoint = f"https://{FORUMS_HOST}/t/{topic_id}.json"
    try:
        response = requests.get(
            endpoint,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=FETCH_TIMEOUT_SECONDS,
        )
    except requests.RequestException as e:
        logger.info("EVE forums topic %s fetch failed: %s", topic_id, e)
        return None
    if response.status_code == 404:
        raise TopicNotFound(topic_id)
    if not response.ok:
        logger.info(
            "EVE forums topic %s fetch returned %s",
            topic_id,
            response.status_code,
        )
        return None
    try:
        data = response.json()
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def in_recruitment_center(topic: dict) -> bool:
    return topic.get("category_id") in RECRUITMENT_CENTER_CATEGORY_IDS
