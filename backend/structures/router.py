from datetime import datetime
from typing import List

from ninja import Router
from pydantic import BaseModel

from .models import EveStructure
from authentication import AuthBearer

router = Router(tags=["Structures"])


class StructureResponse(BaseModel):
    id: int
    name: str
    type: str
    fuel_expires: datetime


@router.get(
    "", auth=AuthBearer(), response={200: List[StructureResponse], 403: None}
)
def get_structures(request):
    if not request.user.has_perm("structures.view_evestructure"):
        return 403, None
    structures = EveStructure.objects.all()
    response = []
    for structure in structures:
        response.append(
            StructureResponse(
                id=structure.id,
                name=structure.name,
                type=structure.type_name,
                fuel_expires=structure.fuel_expires,
            )
        )
    return response
