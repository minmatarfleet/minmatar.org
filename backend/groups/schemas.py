from enum import Enum
from typing import Optional

from pydantic import BaseModel


class GroupStatus(str, Enum):
    AVAILABLE = "available"
    REQUESTED = "requested"
    CONFIRMED = "confirmed"


class GroupSchema(BaseModel):
    id: int
    name: str
    description: Optional[str]
    image_url: Optional[str]
    status: Optional[GroupStatus]
