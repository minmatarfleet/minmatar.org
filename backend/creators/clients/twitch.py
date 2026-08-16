"""Twitch Helix client for creator accounts."""

from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

HELIX_BASE = "https://api.twitch.tv/helix"


class TwitchClient:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.client_id = settings.TWITCH_CLIENT_ID

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Client-Id": self.client_id,
        }

    def get_users(self) -> list[dict[str, Any]]:
        response = requests.get(
            f"{HELIX_BASE}/users",
            headers=self._headers(),
            timeout=15,
        )
        if response.status_code >= 400:
            logger.warning(
                "Twitch users failed: %s %s",
                response.status_code,
                response.text[:200],
            )
            return []
        return response.json().get("data") or []

    def get_streams(self, user_ids: list[str]) -> list[dict[str, Any]]:
        if not user_ids:
            return []
        streams: list[dict[str, Any]] = []
        # Helix allows up to 100 user_id query params per request.
        for i in range(0, len(user_ids), 100):
            chunk = user_ids[i : i + 100]
            params = [("user_id", uid) for uid in chunk]
            response = requests.get(
                f"{HELIX_BASE}/streams",
                headers=self._headers(),
                params=params,
                timeout=15,
            )
            if response.status_code >= 400:
                logger.warning(
                    "Twitch streams failed: %s %s",
                    response.status_code,
                    response.text[:200],
                )
                continue
            streams.extend(response.json().get("data") or [])
        return streams

    def get_videos(
        self, user_id: str, *, first: int = 20
    ) -> list[dict[str, Any]]:
        response = requests.get(
            f"{HELIX_BASE}/videos",
            headers=self._headers(),
            params={"user_id": user_id, "first": min(first, 100)},
            timeout=15,
        )
        if response.status_code >= 400:
            logger.warning(
                "Twitch videos failed: %s %s",
                response.status_code,
                response.text[:200],
            )
            return []
        return response.json().get("data") or []
