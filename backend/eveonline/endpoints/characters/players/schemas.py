"""Request/response schemas for player endpoints."""

from typing import Optional

from pydantic import BaseModel


class EvePlayerResponse(BaseModel):
    id: int
    nickname: Optional[str]
    user_id: int
    primary_character_id: Optional[int]
    prime_time: Optional[str]


class UpdateEvePlayerRequest(BaseModel):
    nickname: Optional[str]
    prime_time: Optional[str]
