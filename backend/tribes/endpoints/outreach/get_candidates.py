"""GET "/{tribe_id}/groups/{group_id}/candidates" - skillset-based recruitment candidates."""

from typing import List, Optional

from ninja import Router

from authentication import AuthBearer
from eveonline.models.characters import EveCharacterSkillset
from tribes.endpoints.outreach.schemas import CandidateSchema
from tribes.helpers import user_can_manage_group
from tribes.models import TribeGroup, TribeGroupOutreach, TribeGroupRequirement

PATH = "/{tribe_id}/groups/{group_id}/candidates"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Alliance characters close to or fully meeting skillset requirements (chiefs/elders).",
    "response": {200: List[CandidateSchema], 403: dict, 404: dict},
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - Outreach"])


def get_candidates(
    request,
    tribe_id: int,
    group_id: int,
    minimum_progress: Optional[float] = 0.75,
):
    tg = TribeGroup.objects.filter(pk=group_id, tribe_id=tribe_id).first()
    if not tg:
        return 404, {"detail": "TribeGroup not found."}
    if not user_can_manage_group(request.user, tg):
        return 403, {"detail": "Chiefs and elders only."}

    skillset_reqs = tg.requirements.filter(
        requirement_type=TribeGroupRequirement.REQUIREMENT_TYPE_SKILLSET
    ).select_related("skillset")

    if not skillset_reqs.exists():
        return 200, []

    already_outreached = set(
        TribeGroupOutreach.objects.filter(tribe_group=tg).values_list(
            "character__character_id", flat=True
        )
    )

    results: List[CandidateSchema] = []
    seen = set()
    for req in skillset_reqs:
        if not req.skillset:
            continue
        qs = EveCharacterSkillset.objects.filter(
            eve_skillset=req.skillset,
            progress__gte=minimum_progress,
        ).select_related("character__user")
        for skill_rec in qs:
            char = skill_rec.character
            key = (char.character_id, req.skillset_id)
            if key in seen:
                continue
            seen.add(key)
            results.append(
                CandidateSchema(
                    character_id=char.character_id,
                    character_name=char.character_name,
                    user_id=char.user_id,
                    skillset_id=req.skillset_id,
                    skillset_name=req.skillset.name,
                    progress=skill_rec.progress,
                    missing_skills=skill_rec.missing_skills or 0,
                    already_outreached=char.character_id in already_outreached,
                )
            )

    results.sort(key=lambda c: c.progress, reverse=True)
    return 200, results


router.get(PATH, **ROUTE_SPEC)(get_candidates)
