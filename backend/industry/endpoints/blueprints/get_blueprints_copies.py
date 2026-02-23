"""GET "copies" - list blueprint copies (BPCs) with owner details. Primary character ID in SQL."""

from typing import List

from django.db.models import F, OuterRef, Subquery, Value
from ninja import Router

from eveonline.models import (
    EveCharacter,
    EveCharacterBlueprint,
    EveCorporationBlueprint,
    EvePlayer,
)
from industry.endpoints.blueprints.schemas import (
    BlueprintCopyResponse,
    BlueprintOwnerResponse,
)

PATH = "copies"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "List blueprint copies (BPCs) with owner entity and primary character id",
    "response": {200: List[BlueprintCopyResponse]},
}

router = Router(tags=["Industry - Blueprints"])


def get_blueprints_copies(request) -> List[BlueprintCopyResponse]:
    # Two single-level Subqueries so OuterRef resolves to blueprint queryset
    char_bpcs = (
        EveCharacterBlueprint.objects.exclude(quantity=-1)
        .select_related("character")
        .annotate(
            _owner_user_id=F("character__user_id"),
            entity_id=F("character__character_id"),
            entity_type=Value("character"),
        )
        .annotate(
            _primary_pk=Subquery(
                EvePlayer.objects.filter(
                    user_id=OuterRef("_owner_user_id")
                ).values("primary_character_id")[:1]
            )
        )
        .annotate(
            primary_character_id=Subquery(
                EveCharacter.objects.filter(id=OuterRef("_primary_pk")).values(
                    "character_id"
                )[:1]
            )
        )
        .order_by("type_id", "item_id")
    )

    corp_bpcs = (
        EveCorporationBlueprint.objects.exclude(quantity=-1)
        .select_related("corporation", "corporation__ceo")
        .annotate(
            _owner_user_id=F("corporation__ceo__user_id"),
            entity_id=F("corporation__corporation_id"),
            entity_type=Value("corporation"),
        )
        .annotate(
            _primary_pk=Subquery(
                EvePlayer.objects.filter(
                    user_id=OuterRef("_owner_user_id")
                ).values("primary_character_id")[:1]
            )
        )
        .annotate(
            primary_character_id=Subquery(
                EveCharacter.objects.filter(id=OuterRef("_primary_pk")).values(
                    "character_id"
                )[:1]
            )
        )
        .order_by("type_id", "item_id")
    )

    out: List[BlueprintCopyResponse] = []
    for row in char_bpcs:
        out.append(
            BlueprintCopyResponse(
                item_id=row.item_id,
                type_id=row.type_id,
                location_id=row.location_id,
                location_flag=row.location_flag,
                material_efficiency=row.material_efficiency,
                time_efficiency=row.time_efficiency,
                quantity=row.quantity,
                runs=row.runs,
                owner=BlueprintOwnerResponse(
                    entity_id=row.entity_id,
                    entity_type=row.entity_type,
                    primary_character_id=getattr(
                        row, "primary_character_id", None
                    ),
                ),
            )
        )
    for row in corp_bpcs:
        out.append(
            BlueprintCopyResponse(
                item_id=row.item_id,
                type_id=row.type_id,
                location_id=row.location_id,
                location_flag=row.location_flag,
                material_efficiency=row.material_efficiency,
                time_efficiency=row.time_efficiency,
                quantity=row.quantity,
                runs=row.runs,
                owner=BlueprintOwnerResponse(
                    entity_id=row.entity_id,
                    entity_type=row.entity_type,
                    primary_character_id=getattr(
                        row, "primary_character_id", None
                    ),
                ),
            )
        )
    return out


router.get(PATH, **ROUTE_SPEC)(get_blueprints_copies)
