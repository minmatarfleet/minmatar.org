"""
Resolve character reprocessing skills and implants for facility refine rates.

Skill type IDs (Resource Processing):
  - Reprocessing: 3385 (+3% yield / level)
  - Reprocessing Efficiency: 3389 (+2% yield / level)
  - Simple Ore Processing: 60377 (+2% / level; Veldspar, Scordite, Plagioclase, …)
  - Coherent Ore Processing: 60378 (+2% / level; Kernite, Omber, …)
  - Ubiquitous Moon Ore Processing: 46152 (+2% / level; Zeolites, …)

Alliance compressed-ore plans cover Tritanium/Pyerite/Mexallon via Veldspar
(Simple) + Zeolites (Ubiquitous) + Plagioclase (Simple). Blend
``ore_processing_level`` is the min of Simple + Ubiquitous so the single refine
rate does not overstate either ore family. Coherent is still resolved for
display / Kernite fallback / future allowlist expansion.

Reprocessing implants (slot 8, refiningYieldMutator as fraction):
  - RX-801 (27175): 0.01
  - RX-802 (27169): 0.02
  - RX-804 (27174): 0.04

When the implant toggle is ON, the best RX found on any jump clone or
``active_implants`` is used. Active-clone matching is intentionally ignored.
If no RX is found (or no character / max skills), assume RX-804 (+4%).
When the toggle is OFF, implant bonus is always 0.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from eveonline.models import EveCharacter, EveCharacterClone, EveCharacterSkill

from industry.helpers.facility_profiles import (
    get_facility_refine_rate,
    get_facility_reprocessing,
)

# Core reprocessing skills
SKILL_REPROCESSING = 3385
SKILL_REPROCESSING_EFFICIENCY = 3389
SKILL_SIMPLE_ORE_PROCESSING = 60377
SKILL_COHERENT_ORE_PROCESSING = 60378
SKILL_UBIQUITOUS_MOON_ORE_PROCESSING = 46152

SKILL_NAMES: Dict[int, str] = {
    SKILL_REPROCESSING: "Reprocessing",
    SKILL_REPROCESSING_EFFICIENCY: "Reprocessing Efficiency",
    SKILL_SIMPLE_ORE_PROCESSING: "Simple Ore Processing",
    SKILL_COHERENT_ORE_PROCESSING: "Coherent Ore Processing",
    SKILL_UBIQUITOUS_MOON_ORE_PROCESSING: "Ubiquitous Moon Ore Processing",
}

# Skills that gate the current compression blend
# (Veldspar + Plagioclase = Simple; Zeolites = Ubiquitous).
BELT_BLEND_ORE_SKILL_IDS: tuple[int, ...] = (
    SKILL_SIMPLE_ORE_PROCESSING,
    SKILL_UBIQUITOUS_MOON_ORE_PROCESSING,
)

# Primary compressed ores → ore-processing skill (matches compressed_ore allowlist).
COMPRESSION_ORE_SKILLS: Tuple[Tuple[str, int], ...] = (
    ("Veldspar", SKILL_SIMPLE_ORE_PROCESSING),
    ("Zeolites", SKILL_UBIQUITOUS_MOON_ORE_PROCESSING),
    ("Plagioclase", SKILL_SIMPLE_ORE_PROCESSING),
)

# Zainou 'Beancounter' Reprocessing RX-* → yield fraction bonus
REPROCESSING_IMPLANT_BONUSES: Dict[int, float] = {
    27175: 0.01,  # RX-801
    27169: 0.02,  # RX-802
    27174: 0.04,  # RX-804
}

RX804_TYPE_ID = 27174
RX804_NAME = "Zainou 'Beancounter' Reprocessing RX-804"

# Best reprocessing implant (RX-804) used when assuming max skills + implant ON,
# or when a character has no RX found anywhere.
MAX_REPROCESSING_IMPLANT_BONUS = 0.04

DEFAULT_SKILL_LEVEL = 5


@dataclass(frozen=True)
class CharacterReprocessingSkills:
    """Resolved skill levels + optional implant bonus for refine_rate()."""

    character_id: int
    character_name: str
    reprocessing_level: int
    reprocessing_efficiency_level: int
    simple_ore_processing_level: int
    coherent_ore_processing_level: int
    ubiquitous_moon_ore_processing_level: int
    # Level applied to the current Veldspar + Plagioclase + Zeolites blend.
    ore_processing_level: int
    implant_bonus: float
    implant_type_id: Optional[int]
    implant_name: Optional[str]
    use_reprocessing_implants: bool

    @property
    def effective_implant(self) -> float:
        """
        Implant bonus used in refine math.

        Toggle OFF → always 0. Toggle ON → fitted RX, or RX-804 if none found.
        """
        if not self.use_reprocessing_implants:
            return 0.0
        if self.implant_bonus > 0:
            return self.implant_bonus
        return MAX_REPROCESSING_IMPLANT_BONUS

    def ore_processing_level_for_skill(self, skill_id: int) -> int:
        """Return the character's level for a specific ore-processing skill."""
        by_id = {
            SKILL_SIMPLE_ORE_PROCESSING: self.simple_ore_processing_level,
            SKILL_COHERENT_ORE_PROCESSING: self.coherent_ore_processing_level,
            SKILL_UBIQUITOUS_MOON_ORE_PROCESSING: (
                self.ubiquitous_moon_ore_processing_level
            ),
        }
        if skill_id not in by_id:
            raise ValueError(f"Unknown ore-processing skill_id {skill_id}")
        return by_id[skill_id]


@dataclass(frozen=True)
class OreRefineYield:
    """Per-ore refine yield at a facility for the compression blend."""

    ore_name: str
    skill_id: int
    skill_name: str
    skill_level: int
    refine_rate: float


def _skill_levels_for_character(
    character: EveCharacter, skill_ids: Sequence[int]
) -> Dict[int, int]:
    rows = EveCharacterSkill.objects.filter(
        character=character, skill_id__in=skill_ids
    ).values_list("skill_id", "skill_level")
    levels = {int(sid): int(level) for sid, level in rows}
    return {sid: levels.get(sid, 0) for sid in skill_ids}


def _implant_type_ids_from_raw(raw) -> List[int]:
    """Extract type IDs from JSON list of dicts or ints."""
    out: List[int] = []
    for item in raw or []:
        if isinstance(item, dict):
            tid = item.get("type_id")
            if tid is not None:
                out.append(int(tid))
        elif isinstance(item, int):
            out.append(int(item))
        elif isinstance(item, str) and item.isdigit():
            out.append(int(item))
    return out


def _implant_type_ids_from_clone(clone: EveCharacterClone) -> List[int]:
    """Extract type IDs from clone.implants JSON (list of dicts or ints)."""
    return _implant_type_ids_from_raw(clone.implants)


def reprocessing_implant_from_type_ids(
    type_ids: Iterable[int],
) -> tuple[float, Optional[int], Optional[str]]:
    """
    Return (bonus, type_id, name) for the best RX reprocessing implant present.

    Only one slot-8 reprocessing implant can be fitted; if multiple match the
    map (tests), pick the highest bonus.
    """
    best_bonus = 0.0
    best_tid: Optional[int] = None
    for tid in type_ids:
        bonus = REPROCESSING_IMPLANT_BONUSES.get(int(tid))
        if bonus is not None and bonus >= best_bonus:
            best_bonus = bonus
            best_tid = int(tid)
    if best_tid is None:
        return 0.0, None, None
    names = {
        27175: "Zainou 'Beancounter' Reprocessing RX-801",
        27169: "Zainou 'Beancounter' Reprocessing RX-802",
        RX804_TYPE_ID: RX804_NAME,
    }
    return best_bonus, best_tid, names.get(best_tid)


def character_reprocessing_implant_type_ids(
    character: EveCharacter,
) -> List[int]:
    """
    Collect implant type IDs from every jump clone plus ESI active_implants.

    Does not prefer ``is_active``; the caller picks the best RX among all IDs.
    """
    tids: List[int] = []
    for jump in EveCharacterClone.objects.filter(character=character):
        tids.extend(_implant_type_ids_from_clone(jump))
    tids.extend(_implant_type_ids_from_raw(character.active_implants))
    return tids


# Back-compat alias for any external callers / older imports.
active_clone_implant_type_ids = character_reprocessing_implant_type_ids


def resolve_character_reprocessing_skills(
    character: EveCharacter,
    *,
    use_reprocessing_implants: bool = False,
) -> CharacterReprocessingSkills:
    """Load stored skills + best RX found on any clone / active_implants."""
    levels = _skill_levels_for_character(
        character,
        (
            SKILL_REPROCESSING,
            SKILL_REPROCESSING_EFFICIENCY,
            SKILL_SIMPLE_ORE_PROCESSING,
            SKILL_COHERENT_ORE_PROCESSING,
            SKILL_UBIQUITOUS_MOON_ORE_PROCESSING,
        ),
    )
    simple = levels[SKILL_SIMPLE_ORE_PROCESSING]
    coherent = levels[SKILL_COHERENT_ORE_PROCESSING]
    ubiquitous = levels[SKILL_UBIQUITOUS_MOON_ORE_PROCESSING]
    # Veldspar/Plagioclase (Simple) + Zeolites (Ubiquitous) → conservative min.
    ore_level = min(levels[sid] for sid in BELT_BLEND_ORE_SKILL_IDS)

    # Always detect best fitted RX for UI; apply only when the implant toggle
    # is on (with RX-804 fallback via ``effective_implant``).
    implant_bonus, implant_tid, implant_name = (
        reprocessing_implant_from_type_ids(
            character_reprocessing_implant_type_ids(character)
        )
    )

    return CharacterReprocessingSkills(
        character_id=character.character_id,
        character_name=character.character_name,
        reprocessing_level=levels[SKILL_REPROCESSING],
        reprocessing_efficiency_level=levels[SKILL_REPROCESSING_EFFICIENCY],
        simple_ore_processing_level=simple,
        coherent_ore_processing_level=coherent,
        ubiquitous_moon_ore_processing_level=ubiquitous,
        ore_processing_level=ore_level,
        implant_bonus=implant_bonus,
        implant_type_id=implant_tid,
        implant_name=implant_name,
        use_reprocessing_implants=use_reprocessing_implants,
    )


def compression_ore_refine_yields(
    facility_key: str,
    *,
    skills: Optional[CharacterReprocessingSkills] = None,
    use_reprocessing_implants: bool = False,
    refine_rate_override: Optional[float] = None,
) -> List[OreRefineYield]:
    """
    Per-ore refine yields for the compression blend at ``facility_key``.

    Uses each ore's processing skill level (Simple vs Ubiquitous, etc.).
    When ``refine_rate_override`` is set, every ore uses that fraction.
    Without a character, assumes all skills at V.
    """
    get_facility_reprocessing(facility_key)

    if refine_rate_override is not None:
        if refine_rate_override <= 0 or refine_rate_override > 1.5:
            raise ValueError(
                "refine_rate must be in (0, 1.5] (fraction, e.g. 0.87)"
            )
        out: List[OreRefineYield] = []
        for ore_name, skill_id in COMPRESSION_ORE_SKILLS:
            level = (
                skills.ore_processing_level_for_skill(skill_id)
                if skills is not None
                else DEFAULT_SKILL_LEVEL
            )
            out.append(
                OreRefineYield(
                    ore_name=ore_name,
                    skill_id=skill_id,
                    skill_name=SKILL_NAMES[skill_id],
                    skill_level=level,
                    refine_rate=refine_rate_override,
                )
            )
        return out

    if skills is not None:
        reprocessing_level = skills.reprocessing_level
        reprocessing_efficiency_level = skills.reprocessing_efficiency_level
        implant = skills.effective_implant
    else:
        reprocessing_level = DEFAULT_SKILL_LEVEL
        reprocessing_efficiency_level = DEFAULT_SKILL_LEVEL
        implant = (
            MAX_REPROCESSING_IMPLANT_BONUS
            if use_reprocessing_implants
            else 0.0
        )

    out = []
    for ore_name, skill_id in COMPRESSION_ORE_SKILLS:
        if skills is not None:
            ore_level = skills.ore_processing_level_for_skill(skill_id)
        else:
            ore_level = DEFAULT_SKILL_LEVEL
        rate = get_facility_refine_rate(
            facility_key,
            reprocessing_level=reprocessing_level,
            reprocessing_efficiency_level=reprocessing_efficiency_level,
            ore_processing_level=ore_level,
            implant=implant,
        )
        out.append(
            OreRefineYield(
                ore_name=ore_name,
                skill_id=skill_id,
                skill_name=SKILL_NAMES[skill_id],
                skill_level=ore_level,
                refine_rate=rate,
            )
        )
    return out


def ore_refine_yields_payload(
    yields: Sequence[OreRefineYield],
) -> List[dict]:
    """Serialize ``OreRefineYield`` rows for planner API responses."""
    return [
        {
            "ore_name": row.ore_name,
            "skill_id": row.skill_id,
            "skill_name": row.skill_name,
            "skill_level": row.skill_level,
            "refine_rate": row.refine_rate,
        }
        for row in yields
    ]


def resolve_refine_rate(
    facility_key: str,
    *,
    character: Optional[EveCharacter] = None,
    use_reprocessing_implants: bool = False,
    refine_rate_override: Optional[float] = None,
) -> tuple[float, str, Optional[CharacterReprocessingSkills]]:
    """
    Resolve refine yield for a facility.

    Skills come from the selected character (or 5/5/5 when omitted).
    Implant bonus is applied only when ``use_reprocessing_implants`` is true:
      - character path → best RX on any clone / active_implants, else RX-804
      - max-skills path → RX-804 (+4%)

    The returned rate is the conservative compression blend (min of Simple +
    Ubiquitous ore-processing). Use ``compression_ore_refine_yields`` for
    per-ore breakdowns.

    Priority:
      1. ``refine_rate_override`` when set (manual UI override)
      2. Character skills (+ optional implant) on facility base
      3. Facility default (skills 5/5/5, implant 0 or RX-804)
    """
    if refine_rate_override is not None:
        if refine_rate_override <= 0 or refine_rate_override > 1.5:
            raise ValueError(
                "refine_rate must be in (0, 1.5] (fraction, e.g. 0.87)"
            )
        return refine_rate_override, "override", None

    if character is not None:
        skills = resolve_character_reprocessing_skills(
            character,
            use_reprocessing_implants=use_reprocessing_implants,
        )
        rate = get_facility_refine_rate(
            facility_key,
            reprocessing_level=skills.reprocessing_level,
            reprocessing_efficiency_level=skills.reprocessing_efficiency_level,
            ore_processing_level=skills.ore_processing_level,
            implant=skills.effective_implant,
        )
        return rate, "character", skills

    # Confirm profile exists; assume max skills (± RX-804 from implant flag).
    get_facility_reprocessing(facility_key)
    implant = (
        MAX_REPROCESSING_IMPLANT_BONUS if use_reprocessing_implants else 0.0
    )
    rate = get_facility_refine_rate(facility_key, implant=implant)
    return rate, "facility_default", None
