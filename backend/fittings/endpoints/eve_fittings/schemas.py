from datetime import datetime
from typing import List

from pydantic import BaseModel, field_validator

from fittings.models import FittingTag


class RefitResponse(BaseModel):
    """Refit API Response"""

    id: int
    name: str
    eft_format: str
    description: str
    created_at: datetime
    updated_at: datetime


class FittingResponse(BaseModel):
    """Fittings API Response"""

    id: int
    name: str
    ship_id: int
    description: str
    created_at: datetime
    updated_at: datetime
    eft_format: str
    minimum_pod: str
    recommended_pod: str
    latest_version: str
    tags: List[str]
    refits: List[RefitResponse]

    @field_validator("tags")
    @classmethod
    def tags_must_be_known(cls, v: List[str]) -> List[str]:
        allowed = {c.value for c in FittingTag}
        for tag in v:
            if tag not in allowed:
                raise ValueError(f"invalid fitting tag: {tag!r}")
        return v
