"""GET /corporations/{corporation_id}/info - get a corporation's info."""

from eveuniverse.models import EveFaction
from ninja import Router

from app.errors import ErrorResponse
from eveonline.endpoints.corporations.schemas import CorporationInfoResponse
from eveonline.helpers.corporations.applications import application_process
from eveonline.helpers.corporations.profile import (
    load_corporation,
    public_profile,
    split_requirements,
    split_timezones,
)
from eveonline.helpers.corporations.summary import corporation_public_summary
from eveonline.models import EveAlliance

router = Router(tags=["Corporations"])


@router.get(
    "corporations/{corporation_id}/info",
    response={200: CorporationInfoResponse, 404: ErrorResponse},
    summary="Get a corporation's public profile",
)
def get_corporation_info(request, corporation_id: int):
    corporation = load_corporation(corporation_id)
    if corporation is None:
        return 404, {"detail": "Corporation not found"}
    response = {
        "corporation_id": corporation.corporation_id,
        "corporation_name": corporation.name,
        "introduction": corporation.introduction,
        "biography": corporation.biography,
        "timezones": split_timezones(corporation.timezones),
        "requirements": split_requirements(corporation.requirements),
        "type": corporation.type,
        "active": corporation.active,
        "trial": corporation.trial,
        **public_profile(corporation),
        "public_summary": corporation_public_summary(corporation),
        "application_process": application_process(corporation.corporation_id),
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
