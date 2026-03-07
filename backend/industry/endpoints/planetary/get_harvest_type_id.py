"""GET "/{type_id}" - harvest drill-down: who harvests this P0 (characters list + per-character entries)."""

from django.db.models import F, Sum, Value
from django.db.models.functions import Coalesce

from eveonline.models import EveCharacter, EveCharacterPlanetOutput
from eveonline.helpers.characters import character_primary

from industry.endpoints.planetary.schemas import (
    CharacterRef,
    HarvestDrillDownItem,
    HarvestDrillDownResponse,
)
from industry.helpers.alliance import get_alliance_character_ids

PATH = "{int:type_id}"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Who harvests this P0 type: list of characters and per-character extractor count, daily quantity",
    "response": {200: HarvestDrillDownResponse},
}


def get_harvest_type_id(request, type_id: int):
    alliance_cids = get_alliance_character_ids()
    qs = (
        EveCharacterPlanetOutput.objects.filter(
            output_type=EveCharacterPlanetOutput.OutputType.HARVESTED,
            eve_type_id=type_id,
            planet__character__character_id__in=alliance_cids,
        )
        .values(
            "planet__character__character_id",
            "planet__character__character_name",
        )
        .annotate(
            extractor_count=Coalesce(
                Sum(Coalesce(F("extractor_count"), Value(0))), Value(0)
            ),
            daily_quantity=Sum("daily_quantity"),
        )
    )
    character_ids = [r["planet__character__character_id"] for r in qs]
    characters = {
        c.character_id: c
        for c in EveCharacter.objects.filter(character_id__in=character_ids)
    }
    result = []
    for r in qs:
        actual_id = r["planet__character__character_id"]
        actual_name = r["planet__character__character_name"] or ""
        actual = CharacterRef(
            character_id=actual_id, character_name=actual_name
        )
        primary_id = actual_id
        primary_name = actual_name
        char = characters.get(actual_id)
        if char:
            try:
                primary = character_primary(char)
            except (AttributeError, TypeError):
                primary = None
            if primary:
                primary_id = primary.character_id
                primary_name = primary.character_name or ""
        primary_ref = CharacterRef(
            character_id=primary_id, character_name=primary_name
        )
        result.append(
            HarvestDrillDownItem(
                primary_character=primary_ref,
                actual_character=actual,
                extractor_count=int(r["extractor_count"] or 0),
                daily_quantity=(
                    float(r["daily_quantity"])
                    if r["daily_quantity"] is not None
                    else None
                ),
            )
        )

    # Unique list of actual characters (for "who harvests this" list)
    seen = set()
    characters = []
    for item in result:
        cid = item.actual_character.character_id
        if cid not in seen:
            seen.add(cid)
            characters.append(item.actual_character)

    return HarvestDrillDownResponse(characters=characters, entries=result)
