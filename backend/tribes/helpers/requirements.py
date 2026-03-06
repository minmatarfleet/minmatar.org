"""
Requirement evaluation helpers.

check_character_meets_requirements: evaluates one EveCharacter against all
TribeGroupRequirements for a TribeGroup and returns a per-requirement compliance dict.

characters_meeting_requirements_batch: evaluates many characters in bulk (2 queries
total for assets + skills) and returns the set of character_ids that meet at least
one requirement. Use for reports over many users/characters.

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
from collections import defaultdict
from typing import Any

from eveonline.models import EveCharacter, EveCharacterAsset
from eveonline.models.characters import EveCharacterSkill
from tribes.models import TribeGroup

logger = logging.getLogger(__name__)


def _check_asset_condition(
    character: EveCharacter, asset_types: list, using: str | None = None
) -> tuple["bool | None", str]:
    """
    OR across asset types: satisfied if the character owns >= minimum_count of any one.
    Returns (None, "") when no asset types are configured.
    Pass `using` to route asset queries to an alternate DB alias (e.g. "production_readonly").
    """
    if not asset_types:
        return None, ""

    for at in asset_types:
        if at.eve_type_id is None:
            continue
        qs = EveCharacterAsset.objects.filter(
            character=character, type_id=at.eve_type_id
        )
        if using:
            qs = qs.using(using)
        # locations is M2M (staging only); empty = any location
        location_ids = list(at.locations.values_list("location_id", flat=True))
        if location_ids:
            qs = qs.filter(location_id__in=location_ids)
        count = qs.count()
        minimum = getattr(at, "minimum_count", 1)
        if count >= minimum:
            name = at.eve_type.name if at.eve_type else str(at.eve_type_id)
            return True, f"Matched {name} ({count} asset(s))"

    return False, f"No qualifying asset found among {len(asset_types)} type(s)"


def _check_skill_condition(
    character: EveCharacter,
    qualifying_skills: list,
    using: str | None = None,
) -> tuple["bool | None", str]:
    """
    AND across skills: satisfied only when the character has ALL listed skills at level.
    Returns (None, "") when no skills are configured.
    Pass `using` to route skill queries to an alternate DB alias (e.g. "production_readonly").
    """
    if not qualifying_skills:
        return None, ""

    missing = []
    for entry in qualifying_skills:
        if entry.eve_type_id is None:
            continue
        qs = EveCharacterSkill.objects.filter(
            character=character,
            skill_id=entry.eve_type_id,
            skill_level__gte=entry.minimum_level,
        )
        if using:
            qs = qs.using(using)
        trained = qs.exists()
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
            loc = ""
            if at.locations.exists():
                loc = " @ staging"
            minimum = getattr(at, "minimum_count", 1)
            labels.append(f"≥{minimum}× {name}{loc}")
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
    character: EveCharacter,
    tribe_group: TribeGroup,
    using: str | None = None,
    requirements: list | None = None,
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

    Pass `using` to route all DB queries through an alternate alias
    (e.g. "production_readonly" for reporting against production data).
    Pass `requirements` to use a pre-loaded list (e.g. from characters_meeting_requirements_batch
    or prefetched once per tribe_group) and avoid re-querying.
    """
    snapshot: dict[str, Any] = {}
    if requirements is None:
        req_qs = tribe_group.requirements.prefetch_related(
            "asset_types__eve_type",
            "asset_types__locations",
            "qualifying_skills__eve_type",
        )
        if using:
            req_qs = req_qs.using(using)
        requirements = list(req_qs.all())

    for req in requirements:
        asset_qs = req.asset_types.select_related("eve_type")
        skill_qs = req.qualifying_skills.select_related("eve_type")
        if using:
            asset_qs = asset_qs.using(using)
            skill_qs = skill_qs.using(using)
        asset_types = list(asset_qs.all())
        qualifying_skills = list(skill_qs.all())

        asset_met, asset_detail = _check_asset_condition(
            character, asset_types, using=using
        )
        skill_met, skill_detail = _check_skill_condition(
            character, qualifying_skills, using=using
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


def characters_meeting_requirements_batch(  # noqa: C901
    characters: list[EveCharacter],
    tribe_group: TribeGroup,
    using: str | None = None,
    requirements: list | None = None,
) -> set[int]:
    """
    Check many characters against the tribe group's requirements using at most
    2 queries (assets + skills). Returns the set of EVE character_ids that meet
    at least one requirement.

    Use this for reports over many users/characters instead of calling
    check_character_meets_requirements per character.
    """
    if not characters:
        return set()

    char_pks = [c.pk for c in characters]

    if requirements is None:
        req_qs = tribe_group.requirements.prefetch_related(
            "asset_types__eve_type",
            "qualifying_skills__eve_type",
        )
        if using:
            req_qs = req_qs.using(using)
        requirements = list(req_qs.all())

    asset_type_ids = set()
    asset_requirements = (
        []
    )  # (req, eve_type_id, minimum_count) — location excluded in batch
    skill_requirements_per_req = []  # list of [(skill_id, min_level), ...]
    for req in requirements:
        asset_qs = req.asset_types.all()
        skill_qs = req.qualifying_skills.all()
        if using:
            asset_qs = asset_qs.using(using)
            skill_qs = skill_qs.using(using)
        at_list = list(asset_qs)
        sq_list = list(skill_qs)
        for at in at_list:
            if at.eve_type_id is not None:
                asset_type_ids.add(at.eve_type_id)
                asset_requirements.append(
                    (req, at.eve_type_id, getattr(at, "minimum_count", 1))
                )
        skill_requirements_per_req.append(
            [
                (s.eve_type_id, s.minimum_level)
                for s in sq_list
                if s.eve_type_id is not None
            ]
        )

    # (char_pk, type_id) -> count (location excluded in batch)
    asset_counts = defaultdict(lambda: defaultdict(int))
    if asset_type_ids:
        qs = EveCharacterAsset.objects.filter(
            character_id__in=char_pks,
            type_id__in=asset_type_ids,
        ).values_list("character_id", "type_id")
        if using:
            qs = qs.using(using)
        for char_pk, type_id in qs.iterator():
            asset_counts[char_pk][type_id] += 1

    # (char_pk, skill_id) -> level
    skill_levels = defaultdict(dict)
    all_skill_ids = set()
    for skills in skill_requirements_per_req:
        for skill_id, _ in skills:
            all_skill_ids.add(skill_id)
    if all_skill_ids:
        qs = EveCharacterSkill.objects.filter(
            character_id__in=char_pks,
            skill_id__in=all_skill_ids,
        ).values_list("character_id", "skill_id", "skill_level")
        if using:
            qs = qs.using(using)
        for char_pk, skill_id, skill_level in qs.iterator():
            skill_levels[char_pk][skill_id] = max(
                skill_levels[char_pk].get(skill_id, 0), skill_level
            )

    req_asset_map = defaultdict(list)
    for req, eve_type_id, min_count in asset_requirements:
        req_asset_map[req.pk].append((eve_type_id, min_count))

    meeting = set()
    for char in characters:
        char_pk = char.pk
        for req_idx, req in enumerate(requirements):
            asset_tuples = req_asset_map.get(req.pk, [])
            skill_tuples = skill_requirements_per_req[req_idx]

            asset_met = None
            if asset_tuples:
                for eve_type_id, min_count in asset_tuples:
                    count = asset_counts[char_pk].get(eve_type_id, 0)
                    if count >= min_count:
                        asset_met = True
                        break
                if asset_met is None:
                    asset_met = False

            skill_met = None
            if skill_tuples:
                for skill_id, min_level in skill_tuples:
                    if skill_levels[char_pk].get(skill_id, 0) < min_level:
                        skill_met = False
                        break
                if skill_met is None:
                    skill_met = True

            if asset_met is None and skill_met is None:
                continue
            if asset_met is None:
                met = skill_met
            elif skill_met is None:
                met = asset_met
            else:
                met = asset_met and skill_met
            if met:
                meeting.add(char.character_id)
                break

    return meeting


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
