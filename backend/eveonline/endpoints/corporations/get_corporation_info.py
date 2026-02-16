"""GET /corporations/{corporation_id}/info - get a corporation's info."""

from eveuniverse.models import EveFaction
from ninja import Router

from app.errors import ErrorResponse
from eveonline.endpoints.corporations.schemas import CorporationInfoResponse
from eveonline.models import EveAlliance, EveCorporation

router = Router(tags=["Corporations"])


@router.get(
    "corporations/{corporation_id}/info",
    response={200: CorporationInfoResponse, 404: ErrorResponse},
    summary="Get a corporation's info",
)
def get_corporation_info(request, corporation_id: int):
    if not EveCorporation.objects.filter(
        corporation_id=corporation_id
    ).exists():
        return 404, {"detail": "Corporation not found"}
    corporation = EveCorporation.objects.get(corporation_id=corporation_id)
    response = {
        "corporation_id": corporation.corporation_id,
        "corporation_name": corporation.name,
        "introduction": corporation.introduction,
        "biography": corporation.biography,
        "timezones": (
            corporation.timezones.strip().split(",")
            if corporation.timezones
            else []
        ),
        "requirements": (
            corporation.requirements.strip().split("\n")
            if corporation.requirements
            else []
        ),
        "type": corporation.type,
        "active": corporation.active,
        "members": [],
    }
    if (
        corporation.alliance
        and EveAlliance.objects.filter(
            alliance_id=corporation.alliance.alliance_id
        ).exists()
    ):
        alliance = EveAlliance.objects.get(
            alliance_id=corporation.alliance.alliance_id
        )
        response["alliance_id"] = alliance.alliance_id
        response["alliance_name"] = alliance.name
    if (
        corporation.faction
        and EveFaction.objects.filter(id=corporation.faction_id).exists()
    ):
        faction = EveFaction.objects.get(id=corporation.faction_id)
        response["faction_id"] = faction.id
        response["faction_name"] = faction.name
    return response
