"""
Requirement evaluation helpers.

check_character_meets_requirements: evaluates one EveCharacter against all
TribeGroupRequirements for a TribeGroup and returns a per-requirement compliance dict.

build_membership_snapshot: evaluates all committed characters at application time
and returns a snapshot suitable for storing as TribeGroupMembership.requirement_snapshot.

Logic:
  Within one TribeGroupRequirement, all defined conditions AND together:
    - qualifying_skills: character must have ALL listed skills at their minimum_level.
    - asset_types: character must own >= minimum_count of ANY listed type.
    - If both are defined, both must be satisfied.

  Across multiple TribeGroupRequirements on the same group, the results OR together:
  a character meets the group's requirements if they satisfy ANY single requirement.
"""

import logging
from typing import Any

from eveonline.models import EveCharacter, EveCharacterAsset
from eveonline.models.characters import EveCharacterSkill
from tribes.models import TribeGroup

logger = logging.getLogger(__name__)


def _check_asset_condition(
    character: EveCharacter, asset_types: list
) -> tuple["bool | None", str]:
    """
    OR across asset types: satisfied if the character owns >= minimum_count of any one.
    Returns (None, "") when no asset types are configured.
    """
    if not asset_types:
        return None, ""

    for at in asset_types:
        if at.eve_type_id is None:
            continue
        qs = EveCharacterAsset.objects.filter(
            character=character, type_id=at.eve_type_id
        )
        if at.location_id:
            qs = qs.filter(location_id=at.location_id)
        count = qs.count()
        if count >= at.minimum_count:
            name = at.eve_type.name if at.eve_type else str(at.eve_type_id)
            return True, f"Matched {name} ({count} asset(s))"

    return False, f"No qualifying asset found among {len(asset_types)} type(s)"


def _check_skill_condition(
    character: EveCharacter, qualifying_skills: list
) -> tuple["bool | None", str]:
    """
    AND across skills: satisfied only when the character has ALL listed skills at level.
    Returns (None, "") when no skills are configured.
    """
    if not qualifying_skills:
        return None, ""

    missing = []
    for entry in qualifying_skills:
        if entry.eve_type_id is None:
            continue
        trained = EveCharacterSkill.objects.filter(
            character=character,
            skill_id=entry.eve_type_id,
            skill_level__gte=entry.minimum_level,
        ).exists()
        if not trained:
            name = (
                entry.eve_type.name
                if entry.eve_type
                else str(entry.eve_type_id)
            )
            missing.append(f"{name} {entry.minimum_level}")

    if missing:
        return False, f"Missing: {', '.join(missing)}"
    return True, "All skills met"


def _combine_conditions(
    asset_met: "bool | None",
    asset_detail: str,
    skill_met: "bool | None",
    skill_detail: str,
) -> tuple[bool, str]:
    """AND the two optional conditions together."""
    if asset_met is None and skill_met is None:
        return False, "No conditions configured"
    if asset_met is None:
        return skill_met, skill_detail
    if skill_met is None:
        return asset_met, asset_detail
    return (
        asset_met and skill_met,
        f"Assets: {asset_detail}; Skills: {skill_detail}",
    )


def _build_requirement_display(
    asset_types: list, qualifying_skills: list
) -> str:
    """Human-readable summary of what the requirement demands."""
    parts = []
    if asset_types:
        labels = []
        for at in asset_types:
            if at.eve_type_id is None:
                continue
            name = at.eve_type.name if at.eve_type else str(at.eve_type_id)
            loc = f" @ {at.location_id}" if at.location_id else ""
            labels.append(f"≥{at.minimum_count}× {name}{loc}")
        parts.append(
            "Own any of: " + (" / ".join(labels) or "(no types configured)")
        )
    if qualifying_skills:
        labels = [
            f"{s.eve_type.name if s.eve_type else s.eve_type_id} {s.minimum_level}"
            for s in qualifying_skills
            if s.eve_type_id is not None
        ]
        parts.append(
            "Skills (all required): "
            + (", ".join(labels) or "(no skills configured)")
        )
    return " AND ".join(parts) if parts else "(no conditions)"


def check_character_meets_requirements(
    character: EveCharacter, tribe_group: TribeGroup
) -> dict[str, Any]:
    """
    Evaluate a single EveCharacter against all TribeGroupRequirements for a TribeGroup.

    Returns a dict keyed by requirement pk:
    {
        "<req_pk>": {
            "display": str,   # human-readable description
            "met": bool,
            "detail": str,    # extra context (e.g. missing skills, matched asset)
        },
        ...
    }

    A requirement is "met" when all of its defined conditions are satisfied (AND).
    The caller can determine overall eligibility by OR-ing the "met" values.
    """
    snapshot: dict[str, Any] = {}
    requirements = tribe_group.requirements.prefetch_related(
        "asset_types__eve_type",
        "qualifying_skills__eve_type",
    ).all()

    for req in requirements:
        asset_types = list(req.asset_types.select_related("eve_type").all())
        qualifying_skills = list(
            req.qualifying_skills.select_related("eve_type").all()
        )

        asset_met, asset_detail = _check_asset_condition(
            character, asset_types
        )
        skill_met, skill_detail = _check_skill_condition(
            character, qualifying_skills
        )
        met, detail = _combine_conditions(
            asset_met, asset_detail, skill_met, skill_detail
        )

        snapshot[str(req.pk)] = {
            "display": _build_requirement_display(
                asset_types, qualifying_skills
            ),
            "met": met,
            "detail": detail,
            "asset_met": asset_met,
            "skill_met": skill_met,
        }

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
