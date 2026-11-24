"""Request bodies for creating and changing tribes and groups."""

from typing import Optional

from pydantic import BaseModel


class TribeCreateRequest(BaseModel):
    name: str
    # Derived from the name when empty; never changes afterwards.
    slug: str = ""
    description: str = ""


class TribeGroupCreateRequest(BaseModel):
    name: str
    description: str = ""


class StructurePatchRequest(BaseModel):
    """Rename, archive (``is_active: false``) or restore."""

    name: Optional[str] = None
    is_active: Optional[bool] = None
