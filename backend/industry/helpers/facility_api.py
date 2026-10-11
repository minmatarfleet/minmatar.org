"""Thin helpers for industry planner facility API responses."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from industry.helpers.cost_indices import fetch_system_cost_indices
from industry.helpers.facility_profiles import (
    AMAMAKE_SYSTEM_NAME,
    AUNER_SYSTEM_NAME,
    BASGERIN_SYSTEM_NAME,
    GUKARLA_SYSTEM_NAME,
    RESBROKO_SYSTEM_NAME,
    FACILITY_PROFILES,
    FACILITY_SYSTEM_IDS,
    FacilityBonuses,
    JobClass,
    RigFit,
    get_facility_profile,
    get_facility_reprocessing,
    get_facility_structures,
    get_facility_system_id,
)

FACILITY_SYSTEM_NAMES: Dict[str, str] = {
    "amamake": AMAMAKE_SYSTEM_NAME,
    "auner": AUNER_SYSTEM_NAME,
    "basgerin": BASGERIN_SYSTEM_NAME,
    "gukarla": GUKARLA_SYSTEM_NAME,
    "resbroko": RESBROKO_SYSTEM_NAME,
}

_JOB_CLASS_LABEL = {
    JobClass.SHIP_MANUFACTURING: "Ship manufacturing",
    JobClass.COMPONENT_MANUFACTURING: "Component manufacturing",
    JobClass.REACTION: "Reaction",
}


def normalize_me_te(value: float) -> float:
    """Accept ME/TE as percent (10) or fraction (0.10)."""
    if value < 0:
        raise ValueError("ME/TE must be non-negative")
    if value > 1.0:
        return value / 100.0
    return value


def facility_key_for_system(system_id: int) -> Optional[str]:
    """Return facility profile key for a solar system, or None."""
    for key, sid in FACILITY_SYSTEM_IDS.items():
        if int(sid) == int(system_id):
            return key
    return None


def _pct_label(fraction: float) -> str:
    """Format a fraction as a signed percent string (0.038 → '+3.8%')."""
    pct = fraction * 100.0
    if abs(pct - round(pct)) < 1e-9:
        body = f"{pct:.0f}"
    else:
        body = f"{pct:.1f}".rstrip("0").rstrip(".")
    if pct > 0:
        return f"+{body}%"
    return f"{body}%"


def _structure_role_effects(bonuses: FacilityBonuses) -> List[str]:
    effects: List[str] = []
    if bonuses.role_me:
        effects.append(f"Role ME {_pct_label(bonuses.role_me)}")
    if bonuses.role_te:
        effects.append(f"Role TE {_pct_label(bonuses.role_te)}")
    if bonuses.structure_isk_bonus:
        effects.append(
            f"Job install cost {_pct_label(-bonuses.structure_isk_bonus)}"
        )
    return effects


def _me_te_effects(label: str, me: float, te: float) -> List[str]:
    effects: List[str] = []
    if me:
        effects.append(f"{label} ME {_pct_label(me)}")
    if te:
        effects.append(f"{label} TE {_pct_label(te)}")
    return effects


def _job_class_effects(bonuses: FacilityBonuses) -> List[str]:
    effects = _structure_role_effects(bonuses)
    effects.extend(_me_te_effects("Rig", bonuses.rig_me, bonuses.rig_te))
    return effects


def _reprocess_effects(key: str) -> List[str]:
    rp = get_facility_reprocessing(key)
    return [
        f"Facility base yield {_pct_label(rp.facility_base_yield())}",
        f"Max-skills refine ≈ {_pct_label(rp.refine_rate())}",
        f"Reprocessing tax {_pct_label(rp.facility_tax)}",
    ]


def _rig_payload(
    rig: RigFit,
    key: str,
    profile: Dict[JobClass, FacilityBonuses],
) -> Dict[str, Any]:
    if rig.job_class is not None:
        bonuses = profile[rig.job_class]
        effects = _me_te_effects(
            _JOB_CLASS_LABEL[rig.job_class], bonuses.rig_me, bonuses.rig_te
        )
    elif rig.aux == "lab":
        effects = [
            "Reduces laboratory research, copy, and invention job times",
        ]
    elif rig.aux == "reprocess":
        effects = _reprocess_effects(key)
    else:
        effects = []
    return {
        "name": rig.name,
        "type_id": rig.type_id,
        "job_class": rig.job_class.value if rig.job_class else None,
        "effects": effects,
    }


def _structure_role_effects_for(
    structure_name: str, profile: Dict[JobClass, FacilityBonuses]
) -> List[str]:
    """Role ME/TE/ISK lines from the first job class using this structure."""
    for job_class in JobClass:
        bonuses = profile[job_class]
        if bonuses.structure_name == structure_name:
            return _structure_role_effects(bonuses)
    return []


def _structures_for_profile(
    key: str, profile: Dict[JobClass, FacilityBonuses]
) -> List[Dict[str, Any]]:
    """Fitted structures with type icons and rigs for the UI."""
    return [
        {
            "role": structure.role,
            "name": structure.name,
            "kind": structure.kind,
            "type_id": structure.type_id,
            "effects": _structure_role_effects_for(structure.name, profile),
            "rigs": [
                _rig_payload(rig, key, profile) for rig in structure.rigs
            ],
        }
        for structure in get_facility_structures(key)
    ]


def list_facility_summaries() -> List[Dict[str, Any]]:
    """Cheap facility list (no ESI)."""
    summaries = []
    for key in sorted(FACILITY_PROFILES):
        summaries.append(facility_summary(key))
    return summaries


def _reprocessing_payload(key: str) -> Dict[str, Any]:
    rp = get_facility_reprocessing(key)
    return {
        "structure_name": rp.structure_name,
        "structure_type_id": rp.structure_type_id,
        "rig_name": rp.rig_name,
        "rig_type_id": rp.rig_type_id,
        "facility_base_yield": rp.facility_base_yield(),
        "refine_rate": rp.refine_rate(),
        "facility_tax": rp.facility_tax,
        "effects": [
            f"Facility base yield {_pct_label(rp.facility_base_yield())}",
            f"Max-skills refine ≈ {_pct_label(rp.refine_rate())}",
            f"Reprocessing tax {_pct_label(rp.facility_tax)}",
        ],
    }


def facility_summary(key: str) -> Dict[str, Any]:
    profile = get_facility_profile(key)
    sample = next(iter(profile.values()))
    return {
        "key": key,
        "system_id": get_facility_system_id(key),
        "system_name": FACILITY_SYSTEM_NAMES.get(key, key),
        "structures": _structures_for_profile(key, profile),
        "system_cost_bonus": sample.system_cost_bonus,
        "facility_tax": sample.facility_tax,
        "scc_surcharge": sample.scc_surcharge,
        "reprocessing": _reprocessing_payload(key),
    }


def facility_detail(key: str) -> Dict[str, Any]:
    """Facility summary plus job-class bonuses and live ESI cost indices."""
    summary = facility_summary(key)
    profile = get_facility_profile(key)
    job_classes = []
    for job_class in JobClass:
        b = profile[job_class]
        job_classes.append(
            {
                "job_class": job_class.value,
                "structure_name": b.structure_name,
                "structure_type_id": b.structure_type_id,
                "rig_name": b.rig_name,
                "rig_type_id": b.rig_type_id,
                "role_me": b.role_me,
                "role_te": b.role_te,
                "rig_me": b.rig_me,
                "rig_te": b.rig_te,
                "structure_isk_bonus": b.structure_isk_bonus,
                "effects": _job_class_effects(b),
            }
        )
    mfg, rxn = fetch_system_cost_indices(summary["system_id"])
    return {
        **summary,
        "job_classes": job_classes,
        "cost_indices": {
            "manufacturing": mfg,
            "reaction": rxn,
        },
        "indices_from_esi": True,
    }


def system_industry(system_id: int) -> Dict[str, Any]:
    """
    System industry view: optional matching freeport profile + live indexes.

    Always attempts ESI for the given system_id.
    """
    key = facility_key_for_system(system_id)
    mfg, rxn = fetch_system_cost_indices(system_id)
    facility = facility_summary(key) if key else None
    return {
        "system_id": int(system_id),
        "system_name": (
            FACILITY_SYSTEM_NAMES.get(key) if key else str(system_id)
        ),
        "facility_key": key,
        "facility": facility,
        "cost_indices": {
            "manufacturing": mfg,
            "reaction": rxn,
        },
        "indices_from_esi": True,
    }
