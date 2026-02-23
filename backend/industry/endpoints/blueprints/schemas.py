"""Response schemas for blueprint list endpoints."""

from typing import Optional

from pydantic import BaseModel


class BlueprintOwnerResponse(BaseModel):
    """Owner of a blueprint: entity id, type, and primary character id (from SQL)."""

    entity_id: int
    entity_type: str  # "character" | "corporation"
    primary_character_id: Optional[int] = None


class BlueprintOriginalResponse(BaseModel):
    """One blueprint original (BPO) with owner details."""

    item_id: int
    type_id: int
    location_id: int
    location_flag: str
    material_efficiency: int
    time_efficiency: int
    runs: int
    owner: BlueprintOwnerResponse


class BlueprintCopyResponse(BaseModel):
    """One blueprint copy (BPC) with owner details."""

    item_id: int
    type_id: int
    location_id: int
    location_flag: str
    material_efficiency: int
    time_efficiency: int
    quantity: int
    runs: int
    owner: BlueprintOwnerResponse
