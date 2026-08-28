"""Resolve buyer reprocessing yield from planner facility + character skills."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from eveonline.models import EveCharacter

from buyback.helpers.ore_names import compressed_buyback_ore_base
from buyback.models import EveBuybackSettings
from industry.helpers.facility_api import FACILITY_SYSTEM_NAMES
from industry.helpers.facility_profiles import get_facility_refine_rate
from industry.helpers.reprocessing_skills import (
    DEFAULT_SKILL_LEVEL,
    MAX_REPROCESSING_IMPLANT_BONUS,
    SKILL_COHERENT_ORE_PROCESSING,
    SKILL_SIMPLE_ORE_PROCESSING,
    SKILL_UBIQUITOUS_MOON_ORE_PROCESSING,
    CharacterReprocessingSkills,
    resolve_refine_rate,
)

# Hangar ore families → Resource Processing skill used at that facility.
ORE_FAMILY_SKILL_IDS: dict[str, int] = {
    "Veldspar": SKILL_SIMPLE_ORE_PROCESSING,
    "Scordite": SKILL_SIMPLE_ORE_PROCESSING,
    "Pyroxeres": SKILL_SIMPLE_ORE_PROCESSING,
    "Plagioclase": SKILL_SIMPLE_ORE_PROCESSING,
    "Omber": SKILL_COHERENT_ORE_PROCESSING,
    "Kernite": SKILL_COHERENT_ORE_PROCESSING,
    "Jaspet": SKILL_COHERENT_ORE_PROCESSING,
    "Hemorphite": SKILL_COHERENT_ORE_PROCESSING,
    "Hedbergite": SKILL_COHERENT_ORE_PROCESSING,
    "Zeolites": SKILL_UBIQUITOUS_MOON_ORE_PROCESSING,
    "Sylvite": SKILL_UBIQUITOUS_MOON_ORE_PROCESSING,
    "Bitumens": SKILL_UBIQUITOUS_MOON_ORE_PROCESSING,
    "Coesite": SKILL_UBIQUITOUS_MOON_ORE_PROCESSING,
}


def _ore_family(name: str) -> str:
    family = compressed_buyback_ore_base(name)
    if family:
        return family
    if name.startswith("Compressed "):
        return name[len("Compressed ") :]
    return name


@dataclass
class PurchaseRefine:
    """Blend rate plus per-ore facility yields for hangar conversion."""

    facility_key: str = ""
    facility_name: str = ""
    refine_rate: float = 0.0
    refine_rate_source: str = ""
    skills: Optional[CharacterReprocessingSkills] = None
    use_reprocessing_implants: bool = False
    _by_family: dict[str, float] = field(default_factory=dict)

    def rate_for_ore(self, name: str) -> float:
        if not self.facility_key:
            return self.refine_rate
        family = _ore_family(name)
        cached = self._by_family.get(family)
        if cached is not None:
            return cached
        skill_id = ORE_FAMILY_SKILL_IDS.get(family)
        if self.skills is None:
            ore_level = DEFAULT_SKILL_LEVEL
            reprocessing_level = DEFAULT_SKILL_LEVEL
            reprocessing_efficiency_level = DEFAULT_SKILL_LEVEL
            implant = (
                MAX_REPROCESSING_IMPLANT_BONUS
                if self.use_reprocessing_implants
                else 0.0
            )
        else:
            reprocessing_level = self.skills.reprocessing_level
            reprocessing_efficiency_level = (
                self.skills.reprocessing_efficiency_level
            )
            implant = self.skills.effective_implant
            if skill_id is not None:
                ore_level = self.skills.ore_processing_level_for_skill(
                    skill_id
                )
            else:
                ore_level = self.skills.ore_processing_level
        rate = get_facility_refine_rate(
            self.facility_key,
            reprocessing_level=reprocessing_level,
            reprocessing_efficiency_level=reprocessing_efficiency_level,
            ore_processing_level=ore_level,
            implant=implant,
        )
        self._by_family[family] = rate
        return rate


def build_purchase_refine(
    *,
    settings: EveBuybackSettings | None = None,
    character: EveCharacter | None = None,
    facility_key: str | None = None,
    use_reprocessing_implants: bool = False,
) -> PurchaseRefine:
    """Facility + character skills, or buyback `ore_refine` when no location."""
    loaded = settings or EveBuybackSettings.load()
    key = (facility_key or "").strip().lower()
    if not key:
        return PurchaseRefine(
            refine_rate=float(loaded.ore_refine),
            refine_rate_source="buyback_settings",
            use_reprocessing_implants=use_reprocessing_implants,
        )
    rate, source, skills = resolve_refine_rate(
        key,
        character=character,
        use_reprocessing_implants=use_reprocessing_implants,
    )
    return PurchaseRefine(
        facility_key=key,
        facility_name=FACILITY_SYSTEM_NAMES.get(key, key),
        refine_rate=rate,
        refine_rate_source=source,
        skills=skills,
        use_reprocessing_implants=use_reprocessing_implants,
    )
