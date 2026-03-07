"""Schemas for mining/systems API."""

from datetime import datetime
from typing import List

from pydantic import BaseModel


# Timer duration in minutes by mining level (1=small 1h, 2=medium 4h20m, 3=large 12h)
MINING_LEVEL_DURATION_MINUTES = {1: 60, 2: 260, 3: 720}


class MiningCompletionRecord(BaseModel):
    completed_at: datetime
    completed_by_username: str | None = None


class MiningSystemResponse(BaseModel):
    system_id: int
    system_name: str
    mining_upgrade_level: int
    power: int
    workforce: int
    last_completion: datetime | None = None
    next_available_at: datetime | None = None
    completions: List[MiningCompletionRecord] = []


class PostCompletionRequest(BaseModel):
    completed_at: datetime | None = None  # default now


class PostCompletionResponse(BaseModel):
    system_id: int
    system_name: str
    mining_upgrade_level: int | None = None
    last_completion: datetime
    next_available_at: datetime | None = None
