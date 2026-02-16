"""GET /corporations/{corporation_id} - get a corporation by ID."""

from eveuniverse.models import EveFaction
from ninja import Router

from authentication import AuthBearer
from eveonline.endpoints.corporations.schemas import CorporationResponse
from eveonline.helpers.characters import user_primary_character
from eveonline.models import EveAlliance, EveCharacter, EveCorporation

router = Router(tags=["Corporations"])


@router.get(
    "corporations/{corporation_id}",
    response=CorporationResponse,
    auth=AuthBearer(),
    summary="Get a corporation by ID",
)
def get_corporation_by_id(request, corporation_id: int):
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
        "directors": [
            {
                "character_id": c.character_id,
                "character_name": c.character_name,
            }
            for c in corporation.directors.all()
        ],
        "recruiters": [
            {
                "character_id": c.character_id,
                "character_name": c.character_name,
            }
            for c in corporation.recruiters.all()
        ],
        "stewards": [
            {
                "character_id": c.character_id,
                "character_name": c.character_name,
            }
            for c in corporation.stewards.all()
        ],
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
    for character in EveCharacter.objects.filter(
        corporation_id=corporation_id
    ):
        payload = {
            "character_id": character.character_id,
            "character_name": character.character_name,
        }
        if character.exempt:
            payload["exempt"] = True
        if character.token:
            payload["registered"] = True
            primary_character = user_primary_character(character.user)
            if (
                primary_character
                and primary_character.character_id != character.character_id
            ):
                payload["primary_character_id"] = (
                    primary_character.character_id
                )
                payload["primary_character_name"] = (
                    primary_character.character_name
                )
        response["members"].append(payload)
    return response
