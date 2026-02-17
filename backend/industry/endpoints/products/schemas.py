"""Schemas for industry products endpoints."""

from typing import List, Optional

from pydantic import BaseModel


class IndustryProductRef(BaseModel):
    """Minimal product reference for relations (supplied_for, supplies)."""

    id: int
    type_id: int
    name: str


class CharacterProducerRef(BaseModel):
    """Character with industry jobs producing this product type (Eve character_id, name)."""

    id: int
    name: str


class CorporationProducerRef(BaseModel):
    """Corporation with industry jobs producing this product type (Eve corporation_id, name)."""

    id: int
    name: str


class IndustryProductListItem(BaseModel):
    """One industry product in list: type, strategy, volume, blueprint/reaction, relations, producers."""

    id: int
    type_id: int
    name: str
    strategy: str
    volume: Optional[float] = None
    blueprint_or_reaction_type_id: Optional[int] = None
    supplied_for: List[IndustryProductRef] = []
    supplies: List[IndustryProductRef] = []
    character_producers: List[CharacterProducerRef] = []
    corporation_producers: List[CorporationProducerRef] = []


class IndustryProductDetail(BaseModel):
    """Full industry product detail: all fields plus supplied_for, supplies, producers."""

    id: int
    type_id: int
    name: str
    strategy: str
    volume: Optional[float] = None
    blueprint_or_reaction_type_id: Optional[int] = None
    supplied_for: List[IndustryProductRef] = []
    supplies: List[IndustryProductRef] = []
    character_producers: List[CharacterProducerRef] = []
    corporation_producers: List[CorporationProducerRef] = []
