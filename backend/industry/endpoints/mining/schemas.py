"""Schemas for mining/systems API."""

from datetime import datetime
from typing import List

from pydantic import BaseModel

# Timer duration in minutes by mining level (1=small 1h, 2=medium 4h20m, 3=large 12h)
MINING_LEVEL_DURATION_MINUTES = {1: 60, 2: 260, 3: 720}


class MiningUpgradeDetail(BaseModel):
    """Installed mining upgrade with type_id for icon display."""

    type_id: int
    name: str


class MiningCompletionRecord(BaseModel):
    completed_at: datetime
    completed_by_username: str | None = None
    site_name: str = ""
    respawn_minutes: int | None = None
    next_available_at: datetime | None = None


class MiningSystemResponse(BaseModel):
    system_id: int
    system_name: str
    mining_upgrade_level: int
    mining_upgrades: List[MiningUpgradeDetail] = []
    power: int
    workforce: int
    last_completion: datetime | None = None
    next_available_at: datetime | None = None
    completions: List[MiningCompletionRecord] = []


class PostCompletionRequest(BaseModel):
    completed_at: datetime | None = None  # default now
    site_name: str | None = (
        None  # anomaly name for respawn lookup (e.g. "Large Veldspar Deposit")
    )


class PostCompletionResponse(BaseModel):
    system_id: int
    system_name: str
    mining_upgrade_level: int | None = None
    site_name: str = ""
    last_completion: datetime
    next_available_at: datetime | None = None
    respawn_minutes: int | None = None
