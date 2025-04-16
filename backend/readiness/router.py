import logging

from ninja import Router
from pydantic import BaseModel
from django.db import connection
from typing import List

from app.errors import ErrorResponse
from authentication import AuthBearer

from groups.helpers import TECH_TEAM, user_in_team

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
    if not (
        request.user.is_superuser or user_in_team(request.user, TECH_TEAM)
    ):
        return 403, "Not authorised"

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                fl.location_name,
                fim.squad_id,
                COUNT(*)
            FROM fleets_evefleetinstancemember fim
                LEFT OUTER JOIN fleets_evefleetinstance fi
                    ON fim.eve_fleet_instance_id = fi.id
                LEFT OUTER JOIN fleets_evefleet f
                    ON fi.eve_fleet_id = f.id
                LEFT OUTER JOIN fleets_evefleetlocation fl
                    ON f.location_id = fl.location_id
            WHERE
                f.type = 'strategic'
            GROUP BY fl.location_name,fim.squad_id
            ORDER BY 1, 2
            """
        )
        data = cursor.fetchall()
    response = ReadinessResponse(summary="Testing", total=len(data), values=[])
    for item in data:
        response.values.append(
            ReadinessResponseDetail(
                key=f"{item[0]}, Squad {item[1]}",
                value=item[2],
            )
        )
    return response
