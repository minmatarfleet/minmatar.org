"""
Requirement evaluation helpers.

check_character_meets_requirements: evaluates one EveCharacter against all
TribeGroupRequirements for a TribeGroup and returns a per-requirement compliance dict.

build_membership_snapshot: evaluates all committed characters at application time
and returns a snapshot suitable for storing as TribeGroupMembership.requirement_snapshot.
"""

import logging
from typing import Any

from eveonline.models import EveCharacter, EveCharacterAsset
from eveonline.models.characters import EveCharacterSkill
from tribes.models import TribeGroup, TribeGroupRequirement

logger = logging.getLogger(__name__)


def check_character_meets_requirements(
    character: EveCharacter, tribe_group: TribeGroup
) -> dict[str, Any]:
    """
    Evaluate a single EveCharacter against all TribeGroupRequirements for a TribeGroup.

    Returns a dict keyed by requirement pk:
    {
        "<req_pk>": {
            "requirement_type": str,
            "display": str,        # human-readable description
            "met": bool,
            "detail": str,         # extra context (e.g. missing skills, asset count)
        },
        ...
    }
    """
    snapshot: dict[str, Any] = {}
    requirements = tribe_group.requirements.prefetch_related(
        "asset_types__eve_type",
        "qualifying_skills__eve_type",
    ).all()

    for req in requirements:
        key = str(req.pk)
        entry: dict[str, Any] = {
            "requirement_type": req.requirement_type,
            "display": str(req),
            "met": False,
            "detail": "",
        }

        if (
            req.requirement_type
            == TribeGroupRequirement.REQUIREMENT_TYPE_ASSET
        ):
            # OR logic: character qualifies if they own >= minimum_count of ANY listed type.
            # Each type carries its own minimum_count and optional location_id.
            asset_types = list(
                req.asset_types.select_related("eve_type").all()
            )
            met = False
            matched_name = None
            matched_count = 0
            for at in asset_types:
                if at.eve_type_id is None:
                    continue
                qs = EveCharacterAsset.objects.filter(
                    character=character,
                    type_id=at.eve_type_id,
                )
                if at.location_id:
                    qs = qs.filter(location_id=at.location_id)
                count = qs.count()
                if count >= at.minimum_count:
                    met = True
                    matched_name = (
                        at.eve_type.name
                        if at.eve_type
                        else str(at.eve_type_id)
                    )
                    matched_count = count
                    break

            def _at_label(at):
                name = at.eve_type.name if at.eve_type else str(at.eve_type_id)
                loc = f" @ {at.location_id}" if at.location_id else ""
                return f"≥{at.minimum_count}× {name}{loc}"

            display_list = (
                " / ".join(
                    _at_label(at)
                    for at in asset_types
                    if at.eve_type_id is not None
                )
                or "(no types configured)"
            )
            entry["met"] = met
            entry["display"] = f"Own any of: {display_list}"
            entry["detail"] = (
                f"Matched {matched_name} ({matched_count} asset(s))"
                if met
                else f"No qualifying asset found among {len(asset_types)} type(s)"
            )

        elif (
            req.requirement_type
            == TribeGroupRequirement.REQUIREMENT_TYPE_SKILL
        ):
            # AND logic: character must have ALL listed skills at their minimum level.
            qualifying_skills = list(
                req.qualifying_skills.select_related("eve_type").all()
            )
            missing = []
            for qs_entry in qualifying_skills:
                if qs_entry.eve_type_id is None:
                    continue
                trained = EveCharacterSkill.objects.filter(
                    character=character,
                    skill_id=qs_entry.eve_type_id,
                    skill_level__gte=qs_entry.minimum_level,
                ).exists()
                if not trained:
                    name = (
                        qs_entry.eve_type.name
                        if qs_entry.eve_type
                        else str(qs_entry.eve_type_id)
                    )
                    missing.append(f"{name} {qs_entry.minimum_level}")
            met = len(missing) == 0 and len(qualifying_skills) > 0
            display_list = (
                ", ".join(
                    f"{s.eve_type.name if s.eve_type else s.eve_type_id} {s.minimum_level}"
                    for s in qualifying_skills
                    if s.eve_type_id is not None
                )
                or "(no skills configured)"
            )
            entry["met"] = met
            entry["display"] = f"Skills (all required): {display_list}"
            entry["detail"] = (
                "All skills met" if met else f"Missing: {', '.join(missing)}"
            )

        snapshot[key] = entry

    return snapshot


def build_membership_snapshot(
    user, tribe_group: TribeGroup, character_ids: list[int]
) -> dict[str, Any]:
    """
    Build the requirement_snapshot for a TribeGroupMembership at application time.
    Evaluates each committed character against all requirements.
    """
    snapshot: dict[str, Any] = {}
    for char_id in character_ids:
        try:
            character = EveCharacter.objects.get(
                character_id=char_id, user=user
            )
        except EveCharacter.DoesNotExist:
            logger.warning(
                "Character character_id=%s does not belong to user %s; skipping snapshot.",
                char_id,
                user,
            )
            continue
        snapshot[str(char_id)] = {
            "character_name": character.character_name,
            "requirements": check_character_meets_requirements(
                character, tribe_group
            ),
        }
    return snapshot
