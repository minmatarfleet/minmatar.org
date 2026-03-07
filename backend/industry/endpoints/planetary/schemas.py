"""Schemas for industry planetary (PI) endpoints."""

from typing import Optional

from pydantic import BaseModel


class CharacterRef(BaseModel):
    """External EVE character reference (character_id, character_name)."""

    character_id: int
    character_name: str


class HarvestOverviewItem(BaseModel):
    """One P0 type in harvest overview."""

    type_id: int
    name: str
    total_extractors: int
    total_daily_quantity: Optional[float] = None


class HarvestDrillDownItem(BaseModel):
    """One row in harvest drill-down: primary + actual character, counts."""

    primary_character: CharacterRef
    actual_character: CharacterRef
    extractor_count: int
    daily_quantity: Optional[float] = None


class ProductionOverviewItem(BaseModel):
    """One type in production overview."""

    type_id: int
    name: str
    total_factories: int
    total_daily_quantity: Optional[float] = None


class ProductionDrillDownItem(BaseModel):
    """One row in production drill-down: primary + actual character, counts."""

    primary_character: CharacterRef
    actual_character: CharacterRef
    factory_count: int
    daily_quantity: Optional[float] = None


class PlanetSummaryItem(BaseModel):
    """One row in planet summary: primary + actual character on this planet."""

    primary_character: CharacterRef
    actual_character: CharacterRef
