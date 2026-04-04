from datetime import datetime
from typing import List

from pydantic import BaseModel

from fittings.endpoints.eve_fittings.schemas import FittingResponse


class DoctrineResponse(BaseModel):
    """Doctrines API Response"""

    id: int
    name: str
    type: str
    created_at: datetime
    updated_at: datetime
    description: str
    primary_fittings: List[FittingResponse]
    secondary_fittings: List[FittingResponse]
    support_fittings: List[FittingResponse]
    sig_ids: List[int]
    location_ids: List[int]


class DoctrineFittingResponse(BaseModel):
    """Fitting in a doctrine"""

    fitting_id: int
    fitting_name: str
    role: str
