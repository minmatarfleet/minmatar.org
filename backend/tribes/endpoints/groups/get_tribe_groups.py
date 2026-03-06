"""GET "/{tribe_id}/groups" - list active groups in a tribe."""

from typing import List

from ninja import Router

from tribes.endpoints.groups.schemas import (
    CharacterRefSchema,
    QualifyingAssetTypeSchema,
    QualifyingSkillSchema,
    RequirementSchema,
    TribeGroupSchema,
)
from tribes.models import Tribe, TribeGroupMembership

PATH = "/{tribe_id}/groups"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "List active groups in a tribe.",
    "response": {200: List[TribeGroupSchema], 404: dict},
}

router = Router(tags=["Tribes - Groups"])


def _user_to_character_ref(user) -> "CharacterRefSchema | None":
    try:
        char = user.eveplayer.primary_character
        if char:
            return CharacterRefSchema(
                character_id=char.character_id,
                character_name=char.character_name,
            )
    except Exception:
        pass
    return None


def get_tribe_groups(request, tribe_id: int):
    tribe = Tribe.objects.filter(pk=tribe_id).first()
    if not tribe:
        return 404, {"detail": "Tribe not found."}

    result = []
    for tg in (
        tribe.groups.filter(is_active=True)
        .select_related("chief__eveplayer__primary_character")
        .prefetch_related(
            "requirements__asset_types__eve_type",
            "requirements__asset_types__locations",
            "requirements__qualifying_skills__eve_type",
        )
    ):
        member_count = TribeGroupMembership.objects.filter(
            tribe_group=tg, status=TribeGroupMembership.STATUS_ACTIVE
        ).count()

        chief_ref = _user_to_character_ref(tg.chief) if tg.chief else None

        result.append(
            TribeGroupSchema(
                id=tg.pk,
                tribe_id=tribe.pk,
                tribe_name=tribe.name,
                name=tg.name,
                description=tg.description,
                discord_channel_id=tg.discord_channel_id,
                chief=chief_ref,
                is_active=tg.is_active,
                member_count=member_count,
                requirements=[
                    RequirementSchema(
                        id=req.pk,
                        asset_types=[
                            QualifyingAssetTypeSchema(
                                type_id=at.eve_type_id,
                                type_name=(
                                    at.eve_type.name if at.eve_type else ""
                                ),
                                location_ids=list(
                                    at.locations.values_list("id", flat=True)
                                ),
                            )
                            for at in req.asset_types.all()
                            if at.eve_type_id
                        ],
                        qualifying_skills=[
                            QualifyingSkillSchema(
                                skill_type_id=s.eve_type_id,
                                skill_name=(
                                    s.eve_type.name if s.eve_type else ""
                                ),
                                minimum_level=s.minimum_level,
                            )
                            for s in req.qualifying_skills.all()
                            if s.eve_type_id
                        ],
                    )
                    for req in tg.requirements.all()
                ],
            )
        )
    return 200, result


router.get(PATH, **ROUTE_SPEC)(get_tribe_groups)
