"""YouTube Data API client for creator accounts."""

from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

YOUTUBE_API = "https://www.googleapis.com/youtube/v3"


class YouTubeClient:
    def __init__(self, access_token: str):
        self.access_token = access_token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"}

    def get_my_channel(self) -> dict[str, Any] | None:
        response = requests.get(
            f"{YOUTUBE_API}/channels",
            headers=self._headers(),
            params={"part": "snippet,contentDetails", "mine": "true"},
            timeout=15,
        )
        if response.status_code >= 400:
            logger.warning(
                "YouTube channels.list failed: %s %s",
                response.status_code,
                response.text[:200],
            )
            return None
        items = response.json().get("items") or []
        return items[0] if items else None

    def list_playlist_items(
        self, playlist_id: str, *, max_results: int = 25
    ) -> list[dict[str, Any]]:
        if not playlist_id:
            return []
        response = requests.get(
            f"{YOUTUBE_API}/playlistItems",
            headers=self._headers(),
            params={
                "part": "snippet,contentDetails",
                "playlistId": playlist_id,
                "maxResults": min(max_results, 50),
            },
            timeout=15,
        )
        if response.status_code >= 400:
            logger.warning(
                "YouTube playlistItems failed: %s %s",
                response.status_code,
                response.text[:200],
            )
            return []
        return response.json().get("items") or []
