import logging

from ninja import Router
from pydantic import BaseModel
from django.db import connection
from typing import List

from app.errors import ErrorResponse
from authentication import AuthBearer

router = Router(tags=["Pilot Readiness and Experience"])

log = logging.getLogger(__name__)


class ReadinessResponseDetail(BaseModel):
    key: str
    value: int


class ReadinessResponse(BaseModel):
    summary: str = ""
    total: int = 0
    values: List[ReadinessResponseDetail]


@router.get(
    "",
    description="Readiness summary",
    auth=AuthBearer(),
    response={
        200: ReadinessResponse,
        403: ErrorResponse,
    },
)
def readiness_summary(request):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT squad_id, COUNT(*)
            FROM fleets_evefleetinstancemember
            GROUP BY squad_id
            ORDER BY squad_id
        """
        )
        data = cursor.fetchall()
    response = ReadinessResponse(summary="Testing", total=len(data), values=[])
    for item in data:
        response.values.append(
            ReadinessResponseDetail(
                key=f"Squad {item[0]}",
                value=item[1],
            )
        )
    return response
