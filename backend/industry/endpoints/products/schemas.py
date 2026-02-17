"""Schemas for industry products endpoints."""

from pydantic import BaseModel


class IndustryProductListItem(BaseModel):
    """One industry product: type info and how we source/use it."""

    id: int
    type_id: int
    name: str
    strategy: str
