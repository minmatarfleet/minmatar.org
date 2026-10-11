"""Schemas for NPSI Discord-button endpoints."""

from typing import Optional

from pydantic import BaseModel


class DiscordNpsiActionRequest(BaseModel):
    discord_user_id: int


class DiscordNpsiActionResponse(BaseModel):
    event_id: int
    status: str
    fleet_id: Optional[int] = None
