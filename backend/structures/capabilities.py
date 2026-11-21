"""What a structure is good for, for the browse cards and location page.

Rigs get a tier (T1, T2 or Faction), the best tier that rig line comes in,
what it builds (for the card icon) and its real bonus per build category in
the structure's security band. Services get their EVE type id so the cards
can show the module icon. Costs come from the cached ESI cost indices and the
planner's facility profiles; nothing here calls ESI."""

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

# Every corporation office is reported at the same price.
OFFICE_FEE_ISK = 50_000_000

TIER_LEVEL = {"T1": 1, "T2": 2, "Faction": 3}

# Security multipliers on Upwell rig bonuses.
ENGINEERING_MULTIPLIER = {"high": 1.0, "low": 1.9, "null": 2.1}
REACTOR_MULTIPLIER = {"high": 1.0, "low": 1.0, "null": 1.1}

# Base material / time bonus by tier, before the security multiplier.
ENGINEERING_BASE = {"T1": (0.02, 0.20), "T2": (0.024, 0.24)}
REACTOR_BASE = {"T1": (0.02, 0.20), "T2": (0.024, 0.24)}
# Thukker rigs: one faction tier, a bigger material bonus on capital parts.
THUKKER_BASE = (0.02, 0.20)
THUKKER_CAPITAL_MATERIALS = 0.037
# Laboratory rigs: time and job cost.
LAB_BASE = {"T1": (0.20, 0.10), "T2": (0.24, 0.12)}
# Reprocessing monitor yield points (T1 1, T2 3) and security bonus.
REPROCESS_POINTS = {"T1": 1, "T2": 3}
REPROCESS_SECURITY = {"high": 0.0, "low": 0.06, "null": 0.12}


@dataclass(frozen=True)
class RigRule:
    words: str  # words in the rig's full name
    use: str  # card icon: subcap | capital | components | research | reactions | reprocessing | modules
    kind: str  # engineering | thukker | reactor | lab | reprocess | other
    categories: tuple  # build categories the bonus applies to
    best: str = "T2"  # best tier this rig line comes in


# Checked in order: "Capital Ship Manufacturing" before "Ship Manufacturing".
RIG_RULES = (
    RigRule(
        "Thukker Advanced Component",
        "components",
        "thukker",
        ("Advanced components", "Advanced capital components"),
        "Faction",
    ),
    RigRule(
        "Thukker Structure and Component",
        "components",
        "thukker",
        ("Capital components", "Structure components"),
        "Faction",
    ),
    RigRule(
        "Basic Capital Component",
        "components",
        "engineering",
        ("Capital components",),
    ),
    RigRule(
        "Capital Ship Manufacturing",
        "capital",
        "engineering",
        ("Capital ships",),
    ),
    RigRule("Ship Manufacturing", "subcap", "engineering", ("Ships",)),
    RigRule("Equipment Manufacturing", "modules", "engineering", ("Modules",)),
    RigRule(
        "Ammunition Manufacturing", "modules", "engineering", ("Ammunition",)
    ),
    RigRule(
        "Drone and Fighter Manufacturing",
        "modules",
        "engineering",
        ("Drones and fighters",),
    ),
    RigRule(
        "Laboratory Optimization",
        "research",
        "lab",
        ("Research, copying and invention",),
    ),
    RigRule("Invention", "research", "lab", ("Invention",)),
    RigRule(
        "Reactor Efficiency",
        "reactions",
        "reactor",
        ("Composite, biochemical and hybrid reactions",),
    ),
    RigRule(
        "Biochemical Reactor",
        "reactions",
        "reactor",
        ("Biochemical reactions",),
    ),
    RigRule(
        "Composite Reactor", "reactions", "reactor", ("Composite reactions",)
    ),
    RigRule("Hybrid Reactor", "reactions", "reactor", ("Hybrid reactions",)),
    RigRule(
        "Reprocessing Monitor", "reprocessing", "reprocess", ("Reprocessing",)
    ),
    RigRule("Ore Grading", "reprocessing", "other", ("Ore reprocessing",)),
    RigRule("Ice Grading", "reprocessing", "other", ("Ice reprocessing",)),
)


def rig_rule(name: str) -> Optional[RigRule]:
    for rule in RIG_RULES:
        if rule.words in name:
            return rule
    return None


def rig_tier(name: str) -> str:
    if "Thukker" in name:
        return "Faction"
    if name.strip().endswith(" II"):
        return "T2"
    return "T1"


def security_band(security: Optional[float]) -> str:
    """EVE rounds security to one decimal for these bands."""
    if security is None:
        return "low"
    rounded = round(security, 1)
    if rounded >= 0.5:
        return "high"
    if rounded > 0.0:
        return "low"
    return "null"


def _pct(fraction: float) -> float:
    return round(fraction * 100, 2)


def _engineering(rule: RigRule, tier: str, band: str) -> List[dict]:
    mult = ENGINEERING_MULTIPLIER[band]
    if rule.kind == "thukker":
        materials, time = THUKKER_BASE
        rows = []
        for category in rule.categories:
            base = (
                THUKKER_CAPITAL_MATERIALS
                if category.startswith(("Capital", "Advanced capital"))
                else materials
            )
            rows.append(
                {
                    "category": category,
                    "materials": _pct(base * mult),
                    "time": _pct(time * mult),
                    "cost": None,
                    "yield_bonus": None,
                }
            )
        return rows
    materials, time = ENGINEERING_BASE.get(tier, ENGINEERING_BASE["T1"])
    return [
        {
            "category": category,
            "materials": _pct(materials * mult),
            "time": _pct(time * mult),
            "cost": None,
            "yield_bonus": None,
        }
        for category in rule.categories
    ]


def rig_bonuses(name: str, security: Optional[float]) -> List[dict]:
    """What the rig does in this structure's security band, per category.

    Percentages are reductions (materials, time, cost) or a yield bonus."""
    rule = rig_rule(name)
    if rule is None:
        return []
    tier = rig_tier(name)
    band = security_band(security)
    if rule.kind in ("engineering", "thukker"):
        return _engineering(rule, tier, band)
    if rule.kind == "reactor":
        materials, time = REACTOR_BASE.get(tier, REACTOR_BASE["T1"])
        mult = REACTOR_MULTIPLIER[band]
        return [
            {
                "category": category,
                "materials": _pct(materials * mult),
                "time": _pct(time * mult),
                "cost": None,
                "yield_bonus": None,
            }
            for category in rule.categories
        ]
    if rule.kind == "lab":
        time, cost = LAB_BASE.get(tier, LAB_BASE["T1"])
        mult = ENGINEERING_MULTIPLIER[band]
        return [
            {
                "category": category,
                "materials": None,
                "time": _pct(time * mult),
                "cost": _pct(cost * mult),
                "yield_bonus": None,
            }
            for category in rule.categories
        ]
    if rule.kind == "reprocess":
        points = REPROCESS_POINTS.get(tier, 1)
        sec = REPROCESS_SECURITY[band]
        # Structure yield before skills: (50 + Rm) * (1 + Sec), as a percent.
        return [
            {
                "category": category,
                "materials": None,
                "time": None,
                "cost": None,
                "yield_bonus": round((50 + points) * (1 + sec), 2),
            }
            for category in rule.categories
        ]
    return []


def rig_details(module: dict, security: Optional[float]) -> dict:
    """Extra fields for one rig on a card: tier, best tier, use, bonuses."""
    name = module.get("name", "")
    rule = rig_rule(name)
    tier = rig_tier(name)
    best = rule.best if rule else "T2"
    return {
        "tier": tier,
        "best_tier": best,
        "is_best": TIER_LEVEL[tier] >= TIER_LEVEL[best],
        "use": rule.use if rule else "other",
        "bonuses": rig_bonuses(name, security),
        "upgrade": _upgrade(name, rule, tier, best, security),
    }


def _upgrade(name, rule, tier, best, security) -> List[dict]:
    """The bonus the best tier would give, when this rig is not it."""
    if rule is None or TIER_LEVEL[tier] >= TIER_LEVEL[best] or best != "T2":
        return []
    better = name.strip()
    better = better[:-2] if better.endswith(" I") else better
    return rig_bonuses(f"{better} II", security)


# Services ------------------------------------------------------------------


def service_type_ids(names: Iterable[str]) -> Dict[str, int]:
    """EVE type ids for Standup service module names, for their icons."""
    wanted = {name for name in names if name}
    if not wanted:
        return {}
    # pylint: disable=import-outside-toplevel
    from eveuniverse.models import EveType

    return dict(
        EveType.objects.filter(name__in=wanted).values_list("name", "id")
    )


# NPC station services from ESI, shown like a structure's service modules:
# (ESI service names, label, the Standup module whose icon stands for it).
# ESI spells the lab service "labratory".
STATION_SERVICES = (
    (
        ("jump-clone-facility", "cloning"),
        "Clone bay",
        "Standup Cloning Center I",
    ),
    (
        ("reprocessing-plant",),
        "Reprocessing",
        "Standup Reprocessing Facility I",
    ),
    (("factory",), "Manufacturing", "Standup Manufacturing Plant I"),
    (("labratory", "laboratory"), "Research", "Standup Research Lab I"),
    (("market",), "Market", "Standup Market Hub I"),
)


def station_service_modules(esi_services: Iterable[str]) -> List[dict]:
    """The station's ESI services as service-module rows, in a fixed order."""
    have = set(esi_services)
    return [
        {"name": module, "label": label, "slot": "service"}
        for names, label, module in STATION_SERVICES
        if have.intersection(names)
    ]


INDUSTRY_SERVICE_WORDS = (
    "Manufacturing Plant",
    "Shipyard",
    "Reactor",
    "Reprocessing Facility",
    "Research Lab",
    "Invention Lab",
)


def is_industry(fitting: Iterable[dict]) -> bool:
    """Has industry rigs or industry services, so the card shows its costs."""
    for module in fitting:
        if module.get("slot") == "rig":
            return True
        if module.get("slot") == "service" and any(
            word in module.get("name", "") for word in INDUSTRY_SERVICE_WORDS
        ):
            return True
    return False


# Costs ---------------------------------------------------------------------


def cost_indices(system_ids: Iterable[int]) -> Dict[int, tuple]:
    """{system_id: (manufacturing, reaction)} from the cached ESI indices."""
    # pylint: disable=import-outside-toplevel
    from industry.models import IndustrySystemCostIndex

    ids = set(system_ids)
    if not ids:
        return {}
    return {
        row[0]: (row[1], row[2])
        for row in IndustrySystemCostIndex.objects.filter(
            solar_system_id__in=ids
        ).values_list("solar_system_id", "manufacturing", "reaction")
    }


def _plain(text: str) -> str:
    return " ".join(text.lower().replace("–", "-").replace("(", " ").split())


def facility_costs(facility_key: Optional[str], location_name: str) -> dict:
    """Facility tax and the faction warfare discount on the system index.

    The discount is system-wide. The tax comes from the planner's freeport
    profile, so it is only known for the freeport structures it describes
    (matched by name); other structures in the system show no tax."""
    empty = {"facility_tax": None, "index_discount": 0.0}
    if not facility_key:
        return empty
    # pylint: disable=import-outside-toplevel
    from industry.helpers.facility_profiles import FACILITY_PROFILES

    profile = FACILITY_PROFILES.get(facility_key) or {}
    if not profile:
        return empty
    discount = next(iter(profile.values())).system_cost_bonus
    own = _plain(location_name.split(" - ", 1)[-1])
    for bonuses in profile.values():
        if own and own in _plain(bonuses.structure_name):
            return {
                "facility_tax": bonuses.facility_tax,
                "index_discount": discount,
            }
    return {"facility_tax": None, "index_discount": discount}
