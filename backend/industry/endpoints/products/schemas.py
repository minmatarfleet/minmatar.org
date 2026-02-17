"""Schemas for industry products endpoints."""

from pydantic import BaseModel


class IndustryProductListItem(BaseModel):
    """One industry product: type info and how we source/use it."""

    id: int
    type_id: int
    name: str
    strategy: str


class PutProductRequest(BaseModel):
    """Request body for creating an industry product by type_id."""

    type_id: int
