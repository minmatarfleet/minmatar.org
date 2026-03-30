"""Response schemas for blueprint list and detail endpoints."""

from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional

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
    blueprint_name: str
    type_name: str
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
    blueprint_name: str
    type_name: str
    location_id: int
    location_flag: str
    material_efficiency: int
    time_efficiency: int
    quantity: int
    runs: int
    owner: BlueprintOwnerResponse


class BlueprintIndustryJobResponse(BaseModel):
    """One industry job that references this blueprint instance (ESI blueprint_id)."""

    job_id: int
    source: Literal["character", "corporation"]
    activity_id: int
    blueprint_type_id: int
    status: str
    installer_id: int
    start_date: datetime
    end_date: datetime
    completed_date: Optional[datetime] = None
    duration: int
    runs: int
    licensed_runs: int
    cost: Optional[Decimal] = None
    location_id: int
    output_location_id: int
    blueprint_location_id: int
    facility_id: int
    character_id: Optional[int] = None
    character_name: Optional[str] = None
    corporation_id: Optional[int] = None
    corporation_name: Optional[str] = None


class BlueprintDetailResponse(BaseModel):
    """Blueprint inventory row plus current and historical jobs for that item_id."""

    item_id: int
    type_id: int
    blueprint_name: str
    type_name: str
    location_id: int
    location_flag: str
    material_efficiency: int
    time_efficiency: int
    quantity: int
    runs: int
    is_original: bool
    owner: BlueprintOwnerResponse
    current_jobs: List[BlueprintIndustryJobResponse]
    historical_jobs: List[BlueprintIndustryJobResponse]
