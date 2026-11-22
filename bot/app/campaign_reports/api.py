"""Calls to the campaigns API for the report commands."""

from __future__ import annotations

import requests
from pydantic import BaseModel

from app.settings import settings

REPORT_URL = f"{settings.API_URL}/campaigns/discord/report"
CAMPAIGNS_URL = f"{settings.API_URL}/campaigns/discord/report-campaigns"
AUTH_HEADERS = {
    "Authorization": f"Bearer {settings.MINMATAR_API_TOKEN}",  # pragma: allowlist secret
}


class ReportError(Exception):
    """A message for the reporter."""


class ReportRequest(BaseModel):
    guild_id: int
    discord_user_id: int
    campaign: str = ""
    kind: str
    structure_type: str
    timer_state: str = ""
    selected_item_window: str
    corporation_name: str = ""
    alliance_name: str = ""
    reinforce_hour: int | None = None


class ReportResult(BaseModel):
    message: str
    campaign: str
    url: str


class ReportCampaign(BaseModel):
    slug: str
    name: str


def submit_report(request: ReportRequest) -> ReportResult:
    response = requests.post(
        REPORT_URL,
        headers=AUTH_HEADERS,
        json=request.model_dump(),
        timeout=30,
    )
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if response.status_code >= 400:
        raise ReportError(
            str(payload.get("detail") or "Couldn't save that. Try again.")
        )
    return ReportResult(**payload)


def list_campaigns(
    guild_id: int, discord_user_id: int
) -> list[ReportCampaign]:
    response = requests.get(
        CAMPAIGNS_URL,
        headers=AUTH_HEADERS,
        params={"guild_id": guild_id, "discord_user_id": discord_user_id},
        timeout=5,
    )
    response.raise_for_status()
    return [ReportCampaign(**row) for row in response.json()]
