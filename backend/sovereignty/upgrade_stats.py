"""
Derive sovereignty upgrade stats from EveType in eveuniverse (dogma) or via ESI.
No management commands or SDE files — uses EveType.dogma_attributes when EVEUNIVERSE_LOAD_DOGMAS
is True, or ESI GET /universe/types/{type_id}/ for dogma_attributes.

ESI does not expose powerAllocation/workforceAllocation on type dogma for sovereignty upgrades,
so we fall back to a known mapping (from SDE sovereigntyUpgrades / game data) when dogma returns nothing.
"""

from dataclasses import dataclass
from typing import Optional

from eveuniverse.models import EveType


@dataclass
class SovereigntyUpgradeStats:
    """Power/workforce and mining level for a sovereignty upgrade EveType."""

    power_cost: int = 0
    workforce_cost: int = 0
    produces_power: Optional[int] = None
    consumes_workforce: Optional[int] = None
    produces_workforce: Optional[int] = None
    consumes_power: Optional[int] = None
    mining_upgrade_level: Optional[int] = None  # 1=small, 2=medium, 3=large


# Dogma attribute names used by EVE for sovereignty upgrades (eveuniverse loads these).
# Allocation = cost; production = generates (and for conversions, consumes the other resource).
ATTR_POWER_ALLOCATION = "powerAllocation"
ATTR_POWER_PRODUCTION = "powerProduction"
ATTR_WORKFORCE_ALLOCATION = "workforceAllocation"
ATTR_WORKFORCE_PRODUCTION = "workforceProduction"


def _stats_from_csv_row(
    power_val: int, workforce_val: int
) -> SovereigntyUpgradeStats:
    """Build SovereigntyUpgradeStats from CSV Power/Workforce columns (negative = produces)."""
    if power_val < 0:
        return SovereigntyUpgradeStats(
            power_cost=0,
            workforce_cost=workforce_val,
            produces_power=abs(power_val),
            consumes_workforce=workforce_val,
        )
    if workforce_val < 0:
        return SovereigntyUpgradeStats(
            power_cost=power_val,
            workforce_cost=0,
            produces_workforce=abs(workforce_val),
            consumes_power=power_val,
        )
    return SovereigntyUpgradeStats(
        power_cost=power_val, workforce_cost=workforce_val
    )


# Fallback when type dogma does not include sovereignty attributes (ESI omits them).
# type_id -> SovereigntyUpgradeStats. Add entries as needed; type_id fallback checked first.
SOV_UPGRADE_STATS_FALLBACK: dict[int, SovereigntyUpgradeStats] = {}

# Name-based fallback from "Bears Sov Planner v3 - Data.csv" (Upgrade, Power, Workforce columns).
# Used when dogma and type_id fallback miss; key = exact EveType name.
SOV_UPGRADE_STATS_BY_NAME: dict[str, SovereigntyUpgradeStats] = {
    "Advanced Logistics Network": _stats_from_csv_row(500, 18100),
    "Cynosural Navigation": _stats_from_csv_row(250, 1500),
    "Cynosural Suppression": _stats_from_csv_row(250, 4500),
    "Electric Stability Generator": _stats_from_csv_row(200, 2700),
    "Exotic Stability Generator": _stats_from_csv_row(200, 2700),
    "Exploration Detector 1": _stats_from_csv_row(400, 4000),
    "Exploration Detector 2": _stats_from_csv_row(850, 8000),
    "Exploration Detector 3": _stats_from_csv_row(1300, 12000),
    "Gamma Stability Generator": _stats_from_csv_row(200, 2700),
    "Isogen Prospecting Array 1": _stats_from_csv_row(500, 6400),
    "Isogen Prospecting Array 2": _stats_from_csv_row(1350, 12700),
    "Isogen Prospecting Array 3": _stats_from_csv_row(1800, 18100),
    "Major Threat Detection Array 1": _stats_from_csv_row(400, 2700),
    "Major Threat Detection Array 2": _stats_from_csv_row(900, 5400),
    "Major Threat Detection Array 3": _stats_from_csv_row(1300, 7300),
    "Megacyte Prospecting Array 1": _stats_from_csv_row(500, 6400),
    "Megacyte Prospecting Array 2": _stats_from_csv_row(1350, 12700),
    "Megacyte Prospecting Array 3": _stats_from_csv_row(1800, 18100),
    "Mexallon Prospecting Array 1": _stats_from_csv_row(500, 6400),
    "Mexallon Prospecting Array 2": _stats_from_csv_row(1350, 12700),
    "Mexallon Prospecting Array 3": _stats_from_csv_row(1800, 18100),
    "Minor Threat Detection Array 1": _stats_from_csv_row(200, 1800),
    "Minor Threat Detection Array 2": _stats_from_csv_row(500, 3800),
    "Minor Threat Detection Array 3": _stats_from_csv_row(700, 5400),
    "Nocxium Prospecting Array 1": _stats_from_csv_row(500, 6400),
    "Nocxium Prospecting Array 2": _stats_from_csv_row(1350, 12700),
    "Nocxium Prospecting Array 3": _stats_from_csv_row(1800, 18100),
    "Plasma Stability Geneartor": _stats_from_csv_row(200, 2700),  # CSV typo
    "Plasma Stability Generator": _stats_from_csv_row(200, 2700),
    "Power Monitoring Division 1": _stats_from_csv_row(-200, 2500),
    "Power Monitoring Division 2": _stats_from_csv_row(-500, 10000),
    "Power Monitoring Division 3": _stats_from_csv_row(-1000, 25000),
    "Pyerite Prospecting Array 1": _stats_from_csv_row(500, 6400),
    "Pyerite Prospecting Array 2": _stats_from_csv_row(1350, 12700),
    "Pyerite Prospecting Array 3": _stats_from_csv_row(1800, 18100),
    "Supercapital Construction Facilities": _stats_from_csv_row(1750, 17500),
    "Tritanium Prospecting Array 1": _stats_from_csv_row(500, 6400),
    "Tritanium Prospecting Array 2": _stats_from_csv_row(1350, 12700),
    "Tritanium Prospecting Array 3": _stats_from_csv_row(1800, 18100),
    "Workforce Mecha-Tooling 1": _stats_from_csv_row(200, -5000),
    "Workforce Mecha-Tooling 2": _stats_from_csv_row(500, -10000),
    "Workforce Mecha-Tooling 3": _stats_from_csv_row(800, -15000),
    "Zydrine Prospecting Array 1": _stats_from_csv_row(500, 6400),
    "Zydrine Prospecting Array 2": _stats_from_csv_row(1350, 12700),
    "Zydrine Prospecting Array 3": _stats_from_csv_row(1800, 18100),
}


def _int_value(val: Optional[float]) -> int:
    if val is None:
        return 0
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return 0


def _get_dogma_value_by_name(
    eve_type: EveType, attr_name: str
) -> Optional[float]:
    """Get dogma attribute value for an EveType by attribute name (eveuniverse)."""
    try:
        qs = eve_type.dogma_attributes.filter(
            eve_dogma_attribute__name=attr_name
        ).values_list("value", flat=True)
        val = qs.first()
        return float(val) if val is not None else None
    except Exception:
        return None


def get_upgrade_stats(eve_type: EveType) -> SovereigntyUpgradeStats:
    """
    Get sovereignty upgrade stats from an EveType using eveuniverse (dogma).
    Loads the type with Section.DOGMAS if needed. Returns zeroed stats if type has no sov attributes.
    Mining level is inferred from type name (Small/Medium/Large + mining or prospecting).
    """
    try:
        EveType.objects.get_or_create_esi(
            id=eve_type.id,
            enabled_sections=[EveType.Section.DOGMAS],
        )
        eve_type = EveType.objects.get(id=eve_type.id)
    except Exception:
        return SovereigntyUpgradeStats()

    power_allocation = _get_dogma_value_by_name(
        eve_type, ATTR_POWER_ALLOCATION
    )
    power_production = _get_dogma_value_by_name(
        eve_type, ATTR_POWER_PRODUCTION
    )
    workforce_allocation = _get_dogma_value_by_name(
        eve_type, ATTR_WORKFORCE_ALLOCATION
    )
    workforce_production = _get_dogma_value_by_name(
        eve_type, ATTR_WORKFORCE_PRODUCTION
    )

    power_cost = _int_value(power_allocation)
    workforce_cost = _int_value(workforce_allocation)
    produces_power = (
        int(power_production) if power_production is not None else None
    )
    produces_workforce = (
        int(workforce_production) if workforce_production is not None else None
    )
    # Conversion: power producer consumes workforce (1:1 with power produced); workforce producer consumes power (power_allocation).
    consumes_workforce = (
        int(power_production) if power_production is not None else None
    )
    consumes_power = (
        power_cost if produces_workforce else None
    )  # workforce producer consumes power_allocation, not workforce_production

    # Mining level: infer from type name (Small=1, Medium=2, Large=3 for mining/prospecting arrays)
    mining_upgrade_level = None
    name = (eve_type.name or "").lower()
    if "small" in name and ("mining" in name or "prospecting" in name):
        mining_upgrade_level = 1
    elif "medium" in name and ("mining" in name or "prospecting" in name):
        mining_upgrade_level = 2
    elif "large" in name and ("mining" in name or "prospecting" in name):
        mining_upgrade_level = 3

    stats = SovereigntyUpgradeStats(
        power_cost=power_cost,
        workforce_cost=workforce_cost,
        produces_power=produces_power if produces_power else None,
        consumes_workforce=consumes_workforce if consumes_workforce else None,
        produces_workforce=produces_workforce if produces_workforce else None,
        consumes_power=consumes_power if consumes_power else None,
        mining_upgrade_level=mining_upgrade_level,
    )
    # ESI type dogma often omits sovereignty attributes; use fallback when nothing from dogma.
    if (
        stats.power_cost == 0
        and stats.workforce_cost == 0
        and stats.produces_power is None
        and stats.produces_workforce is None
    ):
        fallback = SOV_UPGRADE_STATS_FALLBACK.get(eve_type.id)
        if fallback is not None:
            return fallback
        name_fallback = (
            SOV_UPGRADE_STATS_BY_NAME.get(eve_type.name)
            if eve_type.name
            else None
        )
        if name_fallback is not None:
            return name_fallback
    return stats
