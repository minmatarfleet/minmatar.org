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
  - Facility tax 0.75%; reprocessing tax 2.5%

Basgerin (assumed same Sotiyo/Tatara fittings as Amamake; no FW bonus):
  - The Forgery (Sotiyo) + reactions Tatara
  - Facility tax 0.75%; reprocessing tax 2.5%

Auner (scanned — EveGuru Industrial Park; same Sotiyo/Tatara fittings):
  - Guru Forge (Sotiyo) + Guru Foundry (Tatara)
  - Facility tax 1%; reprocessing tax 3%; no FW system-cost bonus

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
from typing import Dict, List, Optional, Tuple


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
    # Structure hull + representative rig for this job class (UI / API only;
    # the numeric bonuses above are what the planner actually costs with).
    structure_kind: str = "sotiyo"
    structure_type_id: int = 0
    rig_name: str = ""
    rig_type_id: int = 0

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
    # Structure hull + representative rig (UI / API only).
    structure_kind: str = "tatara"
    structure_type_id: int = 0
    rig_type_id: int = 0

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


@dataclass(frozen=True)
class RigFit:
    """A fitted Standup rig, for the planner facility card (display only)."""

    name: str
    type_id: int
    # Job class this rig accelerates (drives the ME/TE effect label). None for
    # auxiliary rigs whose bonus the planner does not cost with:
    #   aux="lab" (research), aux="reprocess" (reprocessing yield).
    job_class: Optional[JobClass] = None
    aux: str = ""


@dataclass(frozen=True)
class StructureFit:
    """A fitted freeport structure with its full rig complement (display)."""

    role: str  # "ship" | "component" | "reaction" | "reprocessing"
    name: str  # matches the FacilityBonuses / ReprocessingProfile it backs
    kind: str  # "sotiyo" | "azbel" | "athanor" | "tatara"
    type_id: int
    rigs: Tuple[RigFit, ...] = ()


# --- EVE type IDs: freeport structures + fitted industry rigs ---
SOTIYO_TYPE_ID = 35827
TATARA_TYPE_ID = 35836
AZBEL_TYPE_ID = 35826
ATHANOR_TYPE_ID = 35835

# Sotiyo + Tatara stack (Amamake / Auner / Basgerin).
RIG_XL_SHIP_MFG = RigFit(
    "Standup XL-Set Ship Manufacturing Efficiency I",
    37180,
    JobClass.SHIP_MANUFACTURING,
)
RIG_XL_THUKKER = RigFit(
    "Standup XL-Set Thukker Structure and Component Manufacturing Efficiency",
    45548,
    JobClass.COMPONENT_MANUFACTURING,
)
RIG_XL_LAB = RigFit(
    "Standup XL-Set Laboratory Optimization I", 37183, None, aux="lab"
)
RIG_L_REACTOR_EFF = RigFit(
    "Standup L-Set Reactor Efficiency II", 46497, JobClass.REACTION
)
RIG_L_REPROCESS_MONITOR = RigFit(
    "Standup L-Set Reprocessing Monitor II", 46640, None, aux="reprocess"
)

# Azbel + twin Athanor stack (Gukarla / Resbroko "Hydra" freeports).
RIG_L_CAP_SHIP_MFG = RigFit(
    "Standup L-Set Capital Ship Manufacturing Efficiency I",
    37173,
    JobClass.SHIP_MANUFACTURING,
)
RIG_L_BASIC_CAP_COMPONENT = RigFit(
    "Standup L-Set Basic Capital Component Manufacturing Efficiency I",
    43718,
    JobClass.COMPONENT_MANUFACTURING,
)
RIG_L_THUKKER_ADV_COMPONENT = RigFit(
    "Standup L-Set Thukker Advanced Component Manufacturing Efficiency",
    45641,
    JobClass.COMPONENT_MANUFACTURING,
)
RIG_M_BIOCHEMICAL_REACTOR = RigFit(
    "Standup M-Set Biochemical Reactor Material Efficiency I",
    46494,
    JobClass.REACTION,
)
RIG_M_COMPOSITE_REACTOR = RigFit(
    "Standup M-Set Composite Reactor Material Efficiency I",
    46486,
    JobClass.REACTION,
)
RIG_M_HYBRID_REACTOR = RigFit(
    "Standup M-Set Hybrid Reactor Material Efficiency I",
    46490,
    JobClass.REACTION,
)
RIG_M_ASTEROID_GRADING = RigFit(
    "Standup M-Set Asteroid Ore Grading Processor I",
    46633,
    None,
    aux="reprocess",
)
RIG_M_ICE_GRADING = RigFit(
    "Standup M-Set Ice Grading Processor I", 46635, None, aux="reprocess"
)
RIG_M_MOON_GRADING = RigFit(
    "Standup M-Set Moon Ore Grading Processor I", 46637, None, aux="reprocess"
)


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

# --- Hydra (Azbel + Athanor) rig base bonuses ---
# Standup L-Set Capital Ship Manufacturing Efficiency I (ESI attr 2593/2594).
# NOTE: this rig only benefits *capital* ship builds; the planner applies it
# uniformly to the SHIP_MANUFACTURING class (same limitation the Sotiyo XL ship
# rig does not have — that one benefits all ships), so sub-capital estimates in
# a Hydra Azbel are slightly optimistic. The Azbel is a capital yard in practice.
_CAP_SHIP_RIG_ME_BASE = 0.02
_CAP_SHIP_RIG_TE_BASE = 0.20

# Standup L-Set Basic / Thukker capital component rigs (ESI attr 2593/2594).
_CAP_COMPONENT_RIG_ME_BASE = 0.02
_CAP_COMPONENT_RIG_TE_BASE = 0.20

# Standup M-Set <type> Reactor Material Efficiency I (ESI attr 2714 = -2.0);
# no time bonus. Lowsec reactor multiplier is 1.0 (as Reactor Efficiency II).
_MSET_REACTOR_RIG_ME_BASE = 0.02

# Azbel engineering-complex role bonuses (ESI attr 2600/2601/2602 = .99/.96/.80).
_AZBEL_ROLE_ME = 0.01
_AZBEL_ROLE_TE = 0.20
_AZBEL_ISK_BONUS = 0.04

# Athanor refinery running reactions: no reaction ME/time role bonus (only the
# Tatara carries the -25% reaction-time role bonus).
_ATHANOR_REACTION_ROLE_ME = 0.0
_ATHANOR_REACTION_ROLE_TE = 0.0
_ATHANOR_REACTION_ISK_BONUS = 0.0

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

# Reprocessing: Athanor + Standup M-Set Ore Grading Processors (Gukarla / Resbroko).
# Athanor structure modifier is 0.02 (vs Tatara 0.055). The grading-processor rig
# modifier is derived on the same scale the Monitor II uses: ESI refiningYield
# (attr 717) minus the 0.50 base, ×100 — Monitor II 0.53 → 3.0 calibrates it, so
# the M-Set grading rig 0.51 → 1.0. The three grading rigs cover asteroid / ice /
# moon ore respectively (full ore coverage), each contributing the same modifier.
_ATHANOR_STRUCTURE_MODIFIER = 0.02
_GRADING_PROCESSOR_RIG_MODIFIER = 1.0

AMAMAKE_SYSTEM_ID = 30002537
AMAMAKE_SYSTEM_NAME = "Amamake"
# FW infrastructure hub level 5: -50% facility pricing (applies system-wide).
AMAMAKE_FW_SYSTEM_COST_BONUS = -0.50

BASGERIN_SYSTEM_ID = 30002666
BASGERIN_SYSTEM_NAME = "Basgerin"

AUNER_SYSTEM_ID = 30002059
AUNER_SYSTEM_NAME = "Auner"

# EveGuru Industrial Park (Auner) corp service taxes from structure bio.
_AUNER_FACILITY_TAX = 0.01
_AUNER_REPROCESSING_TAX = 0.03

GUKARLA_SYSTEM_ID = 30002102
GUKARLA_SYSTEM_NAME = "Gukarla"

RESBROKO_SYSTEM_ID = 30002056
RESBROKO_SYSTEM_NAME = "Resbroko"

# Both Hydra freeports sit in FW systems upgraded to -50% facility pricing,
# and use the same corp taxes as Amamake / Basgerin.
HYDRA_FW_SYSTEM_COST_BONUS = -0.50


def _lowsec_tatara_reprocessing(
    tatara_name: str,
    *,
    facility_tax: float = _FREEPORT_REPROCESSING_TAX,
) -> ReprocessingProfile:
    return ReprocessingProfile(
        structure_name=tatara_name,
        rig_name=RIG_L_REPROCESS_MONITOR.name,
        base_yield_percent=50.0,
        rig_modifier=_REPROCESS_MONITOR_II_RIG_MODIFIER,
        security_modifier=_LOWSEC_REPROCESS_SECURITY_MODIFIER,
        structure_modifier=_TATARA_STRUCTURE_MODIFIER,
        facility_tax=facility_tax,
        structure_kind="tatara",
        structure_type_id=TATARA_TYPE_ID,
        rig_type_id=RIG_L_REPROCESS_MONITOR.type_id,
    )


def _athanor_grading_reprocessing(
    athanor_name: str,
    *,
    facility_tax: float = _FREEPORT_REPROCESSING_TAX,
) -> ReprocessingProfile:
    """Athanor + M-Set Ore Grading Processors (Gukarla / Resbroko)."""
    return ReprocessingProfile(
        structure_name=athanor_name,
        rig_name="Standup M-Set Ore Grading Processors (Asteroid / Ice / Moon)",
        base_yield_percent=50.0,
        rig_modifier=_GRADING_PROCESSOR_RIG_MODIFIER,
        security_modifier=_LOWSEC_REPROCESS_SECURITY_MODIFIER,
        structure_modifier=_ATHANOR_STRUCTURE_MODIFIER,
        facility_tax=facility_tax,
        structure_kind="athanor",
        structure_type_id=ATHANOR_TYPE_ID,
        rig_type_id=RIG_M_ASTEROID_GRADING.type_id,
    )


def _lowsec_freeport_bonuses(
    *,
    sotiyo_name: str,
    tatara_name: str,
    system_cost_bonus: float = 0.0,
    facility_tax: float = _FREEPORT_FACILITY_TAX,
) -> Dict[JobClass, FacilityBonuses]:
    """Shared Sotiyo + Tatara fitting stack (Amamake / Basgerin / Auner)."""
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
            structure_kind="sotiyo",
            structure_type_id=SOTIYO_TYPE_ID,
            rig_name=RIG_XL_SHIP_MFG.name,
            rig_type_id=RIG_XL_SHIP_MFG.type_id,
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
            structure_kind="sotiyo",
            structure_type_id=SOTIYO_TYPE_ID,
            rig_name=RIG_XL_THUKKER.name,
            rig_type_id=RIG_XL_THUKKER.type_id,
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
            structure_kind="tatara",
            structure_type_id=TATARA_TYPE_ID,
            rig_name=RIG_L_REACTOR_EFF.name,
            rig_type_id=RIG_L_REACTOR_EFF.type_id,
        ),
    }


def _hydra_freeport_bonuses(
    *,
    azbel_name: str,
    reactions_athanor_name: str,
    system_cost_bonus: float = HYDRA_FW_SYSTEM_COST_BONUS,
    facility_tax: float = _FREEPORT_FACILITY_TAX,
) -> Dict[JobClass, FacilityBonuses]:
    """Azbel manufacturing + Athanor reactions stack (Gukarla / Resbroko)."""
    cap_ship_me = _CAP_SHIP_RIG_ME_BASE * _LOWSEC_ENGINEERING_MULT
    cap_ship_te = _CAP_SHIP_RIG_TE_BASE * _LOWSEC_ENGINEERING_MULT
    cap_comp_me = _CAP_COMPONENT_RIG_ME_BASE * _LOWSEC_ENGINEERING_MULT
    cap_comp_te = _CAP_COMPONENT_RIG_TE_BASE * _LOWSEC_ENGINEERING_MULT
    reactor_me = _MSET_REACTOR_RIG_ME_BASE * _LOWSEC_REACTOR_MULT

    return {
        JobClass.SHIP_MANUFACTURING: FacilityBonuses(
            structure_name=azbel_name,
            role_me=_AZBEL_ROLE_ME,
            role_te=_AZBEL_ROLE_TE,
            rig_me=cap_ship_me,
            rig_te=cap_ship_te,
            structure_isk_bonus=_AZBEL_ISK_BONUS,
            facility_tax=facility_tax,
            system_cost_bonus=system_cost_bonus,
            structure_kind="azbel",
            structure_type_id=AZBEL_TYPE_ID,
            rig_name=RIG_L_CAP_SHIP_MFG.name,
            rig_type_id=RIG_L_CAP_SHIP_MFG.type_id,
        ),
        JobClass.COMPONENT_MANUFACTURING: FacilityBonuses(
            structure_name=azbel_name,
            role_me=_AZBEL_ROLE_ME,
            role_te=_AZBEL_ROLE_TE,
            rig_me=cap_comp_me,
            rig_te=cap_comp_te,
            structure_isk_bonus=_AZBEL_ISK_BONUS,
            facility_tax=facility_tax,
            system_cost_bonus=system_cost_bonus,
            structure_kind="azbel",
            structure_type_id=AZBEL_TYPE_ID,
            rig_name=RIG_L_THUKKER_ADV_COMPONENT.name,
            rig_type_id=RIG_L_THUKKER_ADV_COMPONENT.type_id,
        ),
        JobClass.REACTION: FacilityBonuses(
            structure_name=reactions_athanor_name,
            role_me=_ATHANOR_REACTION_ROLE_ME,
            role_te=_ATHANOR_REACTION_ROLE_TE,
            rig_me=reactor_me,
            rig_te=0.0,
            structure_isk_bonus=_ATHANOR_REACTION_ISK_BONUS,
            facility_tax=facility_tax,
            system_cost_bonus=system_cost_bonus,
            structure_kind="athanor",
            structure_type_id=ATHANOR_TYPE_ID,
            rig_name=RIG_M_BIOCHEMICAL_REACTOR.name,
            rig_type_id=RIG_M_BIOCHEMICAL_REACTOR.type_id,
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


def _auner_bonuses() -> Dict[JobClass, FacilityBonuses]:
    # Same fittings as Amamake; EveGuru taxes; no FW system-cost bonus.
    return _lowsec_freeport_bonuses(
        sotiyo_name="Auner – Guru Forge (Sotiyo)",
        tatara_name="Auner – Guru Foundry (Tatara)",
        system_cost_bonus=0.0,
        facility_tax=_AUNER_FACILITY_TAX,
    )


# Hydra freeport structure names (shared between bonuses, reprocessing, and the
# display registry so they line up).
GUKARLA_AZBEL_NAME = "Gukarla – Hydra Manufacturing (Azbel)"
GUKARLA_REACTIONS_NAME = "Gukarla – Hydra Reactions (Athanor)"
GUKARLA_REPROCESSING_NAME = "Gukarla – Hydra Reprocessing (Athanor)"
RESBROKO_AZBEL_NAME = "Resbroko – Hydra Manufacturing (Azbel)"
RESBROKO_REACTIONS_NAME = "Resbroko – Hydra Reactions (Athanor)"
RESBROKO_REPROCESSING_NAME = "Resbroko – Hydra Reprocessing (Athanor)"


def _gukarla_bonuses() -> Dict[JobClass, FacilityBonuses]:
    return _hydra_freeport_bonuses(
        azbel_name=GUKARLA_AZBEL_NAME,
        reactions_athanor_name=GUKARLA_REACTIONS_NAME,
    )


def _resbroko_bonuses() -> Dict[JobClass, FacilityBonuses]:
    # Same fit as Gukarla (Digital Blink: "resbroko is the same setup").
    return _hydra_freeport_bonuses(
        azbel_name=RESBROKO_AZBEL_NAME,
        reactions_athanor_name=RESBROKO_REACTIONS_NAME,
    )


FACILITY_PROFILES: Dict[str, Dict[JobClass, FacilityBonuses]] = {
    "amamake": _amamake_bonuses(),
    "auner": _auner_bonuses(),
    "basgerin": _basgerin_bonuses(),
    "gukarla": _gukarla_bonuses(),
    "resbroko": _resbroko_bonuses(),
}

FACILITY_REPROCESSING: Dict[str, ReprocessingProfile] = {
    "amamake": _lowsec_tatara_reprocessing(
        "Amamake – Reactions & Reprocessing (Tatara)"
    ),
    "auner": _lowsec_tatara_reprocessing(
        "Auner – Guru Foundry (Tatara)",
        facility_tax=_AUNER_REPROCESSING_TAX,
    ),
    "basgerin": _lowsec_tatara_reprocessing(
        "Basgerin – Reactions & Reprocessing (Tatara)"
    ),
    "gukarla": _athanor_grading_reprocessing(GUKARLA_REPROCESSING_NAME),
    "resbroko": _athanor_grading_reprocessing(RESBROKO_REPROCESSING_NAME),
}

# Solar system used for live ESI industry cost indices per facility profile.
FACILITY_SYSTEM_IDS: Dict[str, int] = {
    "amamake": AMAMAKE_SYSTEM_ID,
    "auner": AUNER_SYSTEM_ID,
    "basgerin": BASGERIN_SYSTEM_ID,
    "gukarla": GUKARLA_SYSTEM_ID,
    "resbroko": RESBROKO_SYSTEM_ID,
}


def _sotiyo_tatara_structures(
    sotiyo_name: str, tatara_name: str
) -> List[StructureFit]:
    """Display fit for the Amamake / Auner / Basgerin stack."""
    return [
        StructureFit(
            role="ship",
            name=sotiyo_name,
            kind="sotiyo",
            type_id=SOTIYO_TYPE_ID,
            rigs=(RIG_XL_SHIP_MFG, RIG_XL_THUKKER, RIG_XL_LAB),
        ),
        StructureFit(
            role="reaction",
            name=tatara_name,
            kind="tatara",
            type_id=TATARA_TYPE_ID,
            rigs=(RIG_L_REACTOR_EFF, RIG_L_REPROCESS_MONITOR),
        ),
    ]


def _hydra_structures(
    azbel_name: str, reactions_name: str, reprocessing_name: str
) -> List[StructureFit]:
    """Display fit for the Gukarla / Resbroko stack (Azbel + twin Athanors)."""
    return [
        StructureFit(
            role="ship",
            name=azbel_name,
            kind="azbel",
            type_id=AZBEL_TYPE_ID,
            rigs=(
                RIG_L_CAP_SHIP_MFG,
                RIG_L_BASIC_CAP_COMPONENT,
                RIG_L_THUKKER_ADV_COMPONENT,
            ),
        ),
        StructureFit(
            role="reaction",
            name=reactions_name,
            kind="athanor",
            type_id=ATHANOR_TYPE_ID,
            rigs=(
                RIG_M_BIOCHEMICAL_REACTOR,
                RIG_M_COMPOSITE_REACTOR,
                RIG_M_HYBRID_REACTOR,
            ),
        ),
        StructureFit(
            role="reprocessing",
            name=reprocessing_name,
            kind="athanor",
            type_id=ATHANOR_TYPE_ID,
            rigs=(
                RIG_M_ASTEROID_GRADING,
                RIG_M_ICE_GRADING,
                RIG_M_MOON_GRADING,
            ),
        ),
    ]


# Fitted structures + rigs per facility, for the planner facility card.
FACILITY_STRUCTURES: Dict[str, List[StructureFit]] = {
    "amamake": _sotiyo_tatara_structures(
        "Amamake – Police Weapons Facility (Sotiyo)",
        "Amamake – Reactions & Reprocessing (Tatara)",
    ),
    "auner": _sotiyo_tatara_structures(
        "Auner – Guru Forge (Sotiyo)",
        "Auner – Guru Foundry (Tatara)",
    ),
    "basgerin": _sotiyo_tatara_structures(
        "Basgerin – The Forgery (Sotiyo)",
        "Basgerin – Reactions & Reprocessing (Tatara)",
    ),
    "gukarla": _hydra_structures(
        GUKARLA_AZBEL_NAME, GUKARLA_REACTIONS_NAME, GUKARLA_REPROCESSING_NAME
    ),
    "resbroko": _hydra_structures(
        RESBROKO_AZBEL_NAME,
        RESBROKO_REACTIONS_NAME,
        RESBROKO_REPROCESSING_NAME,
    ),
}


def get_facility_structures(name: str) -> List[StructureFit]:
    """Fitted structure list for a facility profile (display / API)."""
    key = name.lower().strip()
    if key not in FACILITY_STRUCTURES:
        known = ", ".join(sorted(FACILITY_STRUCTURES))
        raise ValueError(f"Unknown facility profile {name!r}. Known: {known}")
    return FACILITY_STRUCTURES[key]


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
