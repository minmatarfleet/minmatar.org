"""
Hardcoded alliance freeport facility profiles.

Amamake (scanned):
  - Police Weapons Facility (Sotiyo):
      XL Ship Manufacturing Efficiency I
      XL Thukker Structure and Component Manufacturing Efficiency I
      XL Laboratory Optimization I
  - Reactions & Reprocessing (Tatara):
      L Reactor Efficiency II
      L Reprocessing Monitor II
  - FW infrastructure (level 5): -50% facility pricing

Basgerin (assumed same Sotiyo/Tatara fittings as Amamake; no FW bonus):
  - The Forgery (Sotiyo) + reactions Tatara

Lowsec security multiplier for engineering (ship / component) rigs is 1.9.
Reactor Efficiency II uses lowsec multiplier 1.0 (null/WH is 1.1).

Reprocessing (Tatara + L Reprocessing Monitor II) uses the EVE University
Upwell formula (percent terms, then /100):
  yield = (50 + Rm) * (1 + Sec) * (1 + Sm) * skill/implant factors
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Dict


class JobClass(str, Enum):
    SHIP_MANUFACTURING = "ship_manufacturing"
    COMPONENT_MANUFACTURING = "component_manufacturing"
    REACTION = "reaction"


@dataclass(frozen=True)
class FacilityBonuses:
    """Effective ME/TE fractions (0.038 = 3.8%) and ISK cost reduction."""

    structure_name: str
    role_me: float
    role_te: float
    rig_me: float
    rig_te: float
    structure_isk_bonus: float
    facility_tax: float = 0.0
    scc_surcharge: float = 0.04
    # Multiplicative bonus on system-index gross cost (e.g. -0.5 for FW -50%).
    # Does not apply to facility tax or SCC surcharge.
    system_cost_bonus: float = 0.0

    @property
    def effective_me(self) -> float:
        """Combined structure+rig ME when blueprint ME is 0 (for display)."""
        return 1.0 - (1.0 - self.role_me) * (1.0 - self.rig_me)

    @property
    def effective_te(self) -> float:
        """Combined structure+rig TE when blueprint TE is 0 (for display)."""
        return 1.0 - (1.0 - self.role_te) * (1.0 - self.rig_te)


@dataclass(frozen=True)
class ReprocessingProfile:
    """
    Upwell reprocessing yield inputs (EVE University formula).

    Rm: 0 none, 1 T1 Monitor, 3 T2 Monitor
    Sec: 0 HS, 0.06 LS, 0.12 NS/WH (only when a rig is fitted)
    Sm: 0 other, 0.02 Athanor, 0.055 Tatara

    facility_tax is charged on estimated output value (ISK fee / output value).
    """

    structure_name: str
    rig_name: str
    base_yield_percent: float = 50.0
    rig_modifier: float = 0.0
    security_modifier: float = 0.0
    structure_modifier: float = 0.0
    # Corp reprocessing tax on Tatara output value (e.g. 2.5%).
    facility_tax: float = 0.0

    def facility_base_yield(self) -> float:
        """Structure + rig yield as a fraction (before character skills)."""
        return (
            (self.base_yield_percent + self.rig_modifier)
            * (1.0 + self.security_modifier)
            * (1.0 + self.structure_modifier)
        ) / 100.0

    def refine_rate(
        self,
        *,
        reprocessing_level: int = 5,
        reprocessing_efficiency_level: int = 5,
        ore_processing_level: int = 5,
        implant: float = 0.0,
    ) -> float:
        """
        Full reprocessing yield fraction including default max skills.

        Defaults match alliance industry assumptions (skills V, no implant).
        """
        return (
            self.facility_base_yield()
            * (1.0 + reprocessing_level * 0.03)
            * (1.0 + reprocessing_efficiency_level * 0.02)
            * (1.0 + ore_processing_level * 0.02)
            * (1.0 + implant)
        )

    def tax_isk(self, output_value: float) -> int:
        """Corp reprocessing tax on estimated output value."""
        if output_value <= 0 or self.facility_tax <= 0:
            return 0
        return math.floor(output_value * self.facility_tax)


# --- Rig base bonuses (before security multiplier) ---
# Standup XL-Set Ship Manufacturing Efficiency I
_SHIP_RIG_ME_BASE = 0.02
_SHIP_RIG_TE_BASE = 0.20

# Standup XL-Set Thukker Structure and Component Manufacturing Efficiency
# Normal (non-capital-component) ME/TE; capital components use enhanced ME.
_THUKKER_RIG_ME_BASE = 0.02
_THUKKER_RIG_TE_BASE = 0.20
_THUKKER_CAPITAL_ME_BASE = 0.037

# Standup L-Set Reactor Efficiency II
_REACTOR_RIG_ME_BASE = 0.024
_REACTOR_RIG_TE_BASE = 0.24

_LOWSEC_ENGINEERING_MULT = 1.9
_LOWSEC_REACTOR_MULT = 1.0

# Sotiyo manufacturing role bonuses
_SOTIYO_ROLE_ME = 0.01
_SOTIYO_ROLE_TE = 0.30
_SOTIYO_ISK_BONUS = 0.05

# Tatara reaction role bonuses (no ISK cost reduction listed on structure)
_TATARA_ROLE_ME = 0.0
_TATARA_ROLE_TE = 0.25
_TATARA_ISK_BONUS = 0.0

# Corp facility tax on manufacturing / reactions (Amamake + Basgerin tooltips).
_FREEPORT_FACILITY_TAX = 0.0075

# Corp reprocessing tax on Tatara output value (Amamake / Basgerin).
_FREEPORT_REPROCESSING_TAX = 0.025

# Reprocessing: Tatara + Standup L-Set Reprocessing Monitor II in lowsec
_TATARA_STRUCTURE_MODIFIER = 0.055
_REPROCESS_MONITOR_II_RIG_MODIFIER = 3.0  # T2
_LOWSEC_REPROCESS_SECURITY_MODIFIER = 0.06

AMAMAKE_SYSTEM_ID = 30002537
AMAMAKE_SYSTEM_NAME = "Amamake"
# FW infrastructure hub level 5: -50% facility pricing (applies system-wide).
AMAMAKE_FW_SYSTEM_COST_BONUS = -0.50

BASGERIN_SYSTEM_ID = 30002666
BASGERIN_SYSTEM_NAME = "Basgerin"


def _lowsec_tatara_reprocessing(tatara_name: str) -> ReprocessingProfile:
    return ReprocessingProfile(
        structure_name=tatara_name,
        rig_name="Standup L-Set Reprocessing Monitor II",
        base_yield_percent=50.0,
        rig_modifier=_REPROCESS_MONITOR_II_RIG_MODIFIER,
        security_modifier=_LOWSEC_REPROCESS_SECURITY_MODIFIER,
        structure_modifier=_TATARA_STRUCTURE_MODIFIER,
        facility_tax=_FREEPORT_REPROCESSING_TAX,
    )


def _lowsec_freeport_bonuses(
    *,
    sotiyo_name: str,
    tatara_name: str,
    system_cost_bonus: float = 0.0,
    facility_tax: float = _FREEPORT_FACILITY_TAX,
) -> Dict[JobClass, FacilityBonuses]:
    """Shared Sotiyo + Tatara fitting stack used by Amamake / Basgerin."""
    ship_rig_me = _SHIP_RIG_ME_BASE * _LOWSEC_ENGINEERING_MULT
    ship_rig_te = _SHIP_RIG_TE_BASE * _LOWSEC_ENGINEERING_MULT
    thukker_me = _THUKKER_RIG_ME_BASE * _LOWSEC_ENGINEERING_MULT
    thukker_te = _THUKKER_RIG_TE_BASE * _LOWSEC_ENGINEERING_MULT
    reactor_me = _REACTOR_RIG_ME_BASE * _LOWSEC_REACTOR_MULT
    reactor_te = _REACTOR_RIG_TE_BASE * _LOWSEC_REACTOR_MULT

    return {
        JobClass.SHIP_MANUFACTURING: FacilityBonuses(
            structure_name=sotiyo_name,
            role_me=_SOTIYO_ROLE_ME,
            role_te=_SOTIYO_ROLE_TE,
            rig_me=ship_rig_me,
            rig_te=ship_rig_te,
            structure_isk_bonus=_SOTIYO_ISK_BONUS,
            facility_tax=facility_tax,
            system_cost_bonus=system_cost_bonus,
        ),
        JobClass.COMPONENT_MANUFACTURING: FacilityBonuses(
            structure_name=sotiyo_name,
            role_me=_SOTIYO_ROLE_ME,
            role_te=_SOTIYO_ROLE_TE,
            rig_me=thukker_me,
            rig_te=thukker_te,
            structure_isk_bonus=_SOTIYO_ISK_BONUS,
            facility_tax=facility_tax,
            system_cost_bonus=system_cost_bonus,
        ),
        JobClass.REACTION: FacilityBonuses(
            structure_name=tatara_name,
            role_me=_TATARA_ROLE_ME,
            role_te=_TATARA_ROLE_TE,
            rig_me=reactor_me,
            rig_te=reactor_te,
            structure_isk_bonus=_TATARA_ISK_BONUS,
            facility_tax=facility_tax,
            system_cost_bonus=system_cost_bonus,
        ),
    }


def _amamake_bonuses() -> Dict[JobClass, FacilityBonuses]:
    return _lowsec_freeport_bonuses(
        sotiyo_name="Amamake – Police Weapons Facility (Sotiyo)",
        tatara_name="Amamake – Reactions & Reprocessing (Tatara)",
        system_cost_bonus=AMAMAKE_FW_SYSTEM_COST_BONUS,
    )


def _basgerin_bonuses() -> Dict[JobClass, FacilityBonuses]:
    # Same fittings as Amamake; no faction warfare facility-pricing bonus.
    return _lowsec_freeport_bonuses(
        sotiyo_name="Basgerin – The Forgery (Sotiyo)",
        tatara_name="Basgerin – Reactions & Reprocessing (Tatara)",
        system_cost_bonus=0.0,
    )


FACILITY_PROFILES: Dict[str, Dict[JobClass, FacilityBonuses]] = {
    "amamake": _amamake_bonuses(),
    "basgerin": _basgerin_bonuses(),
}

FACILITY_REPROCESSING: Dict[str, ReprocessingProfile] = {
    "amamake": _lowsec_tatara_reprocessing(
        "Amamake – Reactions & Reprocessing (Tatara)"
    ),
    "basgerin": _lowsec_tatara_reprocessing(
        "Basgerin – Reactions & Reprocessing (Tatara)"
    ),
}

# Solar system used for live ESI industry cost indices per facility profile.
FACILITY_SYSTEM_IDS: Dict[str, int] = {
    "amamake": AMAMAKE_SYSTEM_ID,
    "basgerin": BASGERIN_SYSTEM_ID,
}

# Thukker enhanced capital-component ME (lowsec), for Advanced Capital Construction
# Components. Not used for Typhoon T1 advanced components (group Construction Components).
THUKKER_CAPITAL_COMPONENT_RIG_ME = (
    _THUKKER_CAPITAL_ME_BASE * _LOWSEC_ENGINEERING_MULT
)


def get_facility_profile(name: str) -> Dict[JobClass, FacilityBonuses]:
    key = name.lower().strip()
    if key not in FACILITY_PROFILES:
        known = ", ".join(sorted(FACILITY_PROFILES))
        raise ValueError(f"Unknown facility profile {name!r}. Known: {known}")
    return FACILITY_PROFILES[key]


def get_facility_system_id(name: str) -> int:
    """Solar system id for live cost-index lookups for this facility profile."""
    key = name.lower().strip()
    if key not in FACILITY_SYSTEM_IDS:
        known = ", ".join(sorted(FACILITY_SYSTEM_IDS))
        raise ValueError(f"Unknown facility profile {name!r}. Known: {known}")
    return FACILITY_SYSTEM_IDS[key]


def get_facility_reprocessing(name: str) -> ReprocessingProfile:
    """Reprocessing (Tatara + Monitor rig) profile for a freeport key."""
    key = name.lower().strip()
    if key not in FACILITY_REPROCESSING:
        known = ", ".join(sorted(FACILITY_REPROCESSING))
        raise ValueError(f"Unknown facility profile {name!r}. Known: {known}")
    return FACILITY_REPROCESSING[key]


def get_facility_refine_rate(
    name: str,
    *,
    reprocessing_level: int = 5,
    reprocessing_efficiency_level: int = 5,
    ore_processing_level: int = 5,
    implant: float = 0.0,
) -> float:
    """Refine yield fraction from facility structure/rigs + character skills."""
    return get_facility_reprocessing(name).refine_rate(
        reprocessing_level=reprocessing_level,
        reprocessing_efficiency_level=reprocessing_efficiency_level,
        ore_processing_level=ore_processing_level,
        implant=implant,
    )


def get_facility_reprocessing_tax(name: str) -> float:
    """Corp reprocessing tax fraction on estimated output value."""
    return get_facility_reprocessing(name).facility_tax
