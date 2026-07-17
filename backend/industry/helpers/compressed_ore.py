"""
Convert a leaf bill of materials into compressed ore for Trit / Pye / Mex.

Current scope (see COMPRESSION_COVERED_MINERALS — extend that allowlist later):
1. Cover Tritanium, Pyerite, and Mexallon with compressed ore at the given
   refine rate.
2. Keep all other minerals, PI, ice, and misc leaves as direct imports.

Isolation ranking (100M mineral @ 84% refine, Compressed * volumes):
- Tritanium → **Veldspar** (≈29.8k m³, zero overage). Scordite is ~4× bulkier
  and dumps Pyerite.
- Pyerite → **Zeolites** (≈149k m³, zero Trit overage). Beats Scordite
  (≈180k m³ + 151M Trit dump). Matches Janice's Compressed Zeolites pick.
  Scordite kept as marketable fallback only.
- Mexallon → **Plagioclase** (≈595k m³). Beats Pyroxeres (≈1.19M m³ + Pye
  dump), Kernite (≈2.38M m³ + 200M Isogen dump), and sizing moon ore for Mex
  (≈2.98M m³ + huge Pye dump). Trit overage from Plagioclase is creditable
  against Trit demand. Kylixium is denser but is not a highsec Janice path.

Blend when Trit + Pye + Mex are needed (order matters for byproduct credit):
1. Size Zeolites for Pyerite demand (credit Mexallon / incidental minerals).
2. Size Plagioclase for remaining Mexallon (credit Tritanium byproduct).
   Never size Zeolites/Scordite/Kernite for Mex when Plagioclase is available.
3. Size Veldspar for remaining Tritanium (never size Pye/Mex ores for Trit).

Moon-ore → PI P0 conversion is implemented but gated off until those materials
are added to COMPRESSION_COVERED_OTHER. Zeolites used for Pyerite still produce
Atmospheric Gases as refine byproduct (tracked in expected outputs).

Modern CCP compression is 1 uncompressed unit → 1 Compressed unit (volume only
shrinks). Yields use EveTypeMaterial on the base ore (portion size 100).

When EveMarketPrice rows exist, only recommend Compressed types that have a
positive average_price (proxy for Jita/universe market availability).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from eveuniverse.models import EveMarketPrice, EveType, EveTypeMaterial

from industry.helpers.producers import DEFAULT_REFINE_RATE, ORE_BATCH_SIZE
from moons.models import ore_yield_map

MINERAL_NAMES = frozenset(
    {
        "Tritanium",
        "Pyerite",
        "Mexallon",
        "Isogen",
        "Nocxium",
        "Zydrine",
        "Megacyte",
        "Morphite",
    }
)

# Minerals satisfied via compressed highsec belt ore. Extend this set (and
# BASE_BELT_ORES) when adding more compression coverage.
COMPRESSION_COVERED_MINERALS: frozenset[str] = frozenset(
    {"Tritanium", "Pyerite", "Mexallon"}
)

# Non-mineral materials covered via compressed ore (e.g. PI P0 via moon ore).
# Empty for now — those stay as direct imports.
COMPRESSION_COVERED_OTHER: frozenset[str] = frozenset()

# Back-compat alias used by belt-blend import gating.
HIGHSEC_BELT_MINERALS = COMPRESSION_COVERED_MINERALS

PI_P0_NAMES = frozenset(
    {
        "Hydrocarbons",
        "Atmospheric Gases",
        "Evaporite Deposits",
        "Silicates",
    }
)

ICE_NAMES = frozenset(
    {
        "Heavy Water",
        "Liquid Ozone",
        "Strontium Clathrates",
        "Helium Isotopes",
        "Hydrogen Isotopes",
        "Nitrogen Isotopes",
        "Oxygen Isotopes",
    }
)

# Highsec moon ores that yield PI P0 (from moons.models.ore_yield_map /
# EveTypeMaterial). Prefer base Compressed forms that trade on the market.
HIGHSEC_MOON_ORES: Dict[str, str] = {
    "Bitumens": "Hydrocarbons",
    "Zeolites": "Atmospheric Gases",
    "Sylvite": "Evaporite Deposits",
    "Coesite": "Silicates",
}

# Compression ores for Trit / Pye / Mex (isolation-optimal + fallbacks).
# Veldspar = Trit; Zeolites = Pye; Plagioclase = Mex; Scordite/Pyroxeres/Kernite
# are marketable fallbacks only.
BASE_BELT_ORES: Tuple[str, ...] = (
    "Veldspar",
    "Zeolites",
    "Plagioclase",
    "Scordite",
    "Pyroxeres",
    "Kernite",
)

# Declared primary ore per allowlisted mineral (from isolation ranking).
# Runtime selection still ranks by yield/m³ among available candidates.
PRIMARY_BELT_ORE_FOR_MINERAL: Dict[str, str] = {
    "Tritanium": "Veldspar",
    "Pyerite": "Zeolites",
    "Mexallon": "Plagioclase",
}

# Ores reserved for Pyerite coverage — never sized for Mex or Trit.
_PYE_ORES: frozenset[str] = frozenset({"Zeolites", "Scordite"})

# Compressed unit volume (m³). Used to pick the densest mineral source.
# Matches modern Compressed * types (not Batch Compressed).
COMPRESSED_ORE_VOLUME_M3: Dict[str, float] = {
    "Veldspar": 0.001,
    "Scordite": 0.0015,
    "Pyroxeres": 0.003,
    "Plagioclase": 0.0035,
    "Kernite": 0.012,
    "Zeolites": 0.1,
}

# Fallback SDE yields per 100 units when TypeMaterials are not loaded.
# Scordite Pyerite 99 / Zeolites 8000 / Plagioclase Mex 70 match TypeMaterials.
FALLBACK_BELT_ORE_YIELDS_PER_100: Dict[str, Dict[str, float]] = {
    "Scordite": {"Tritanium": 150, "Pyerite": 99},
    "Pyroxeres": {"Pyerite": 90, "Mexallon": 30},
    "Plagioclase": {"Tritanium": 175, "Mexallon": 70},
    "Kernite": {"Mexallon": 60, "Isogen": 120},
    "Veldspar": {"Tritanium": 400},
    "Zeolites": {
        "Atmospheric Gases": 65,
        "Pyerite": 8000,
        "Mexallon": 400,
    },
}

# Moon ore fallbacks per 100 units (matches ore_yield_map / 1000 m³ at 10 m³/unit).
FALLBACK_MOON_YIELDS_PER_100: Dict[str, Dict[str, float]] = {
    "Bitumens": {"Hydrocarbons": 65, "Pyerite": 6000, "Mexallon": 400},
    "Zeolites": {"Atmospheric Gases": 65, "Pyerite": 8000, "Mexallon": 400},
    "Sylvite": {"Evaporite Deposits": 65, "Pyerite": 4000, "Mexallon": 400},
    "Coesite": {"Silicates": 65, "Pyerite": 2000, "Mexallon": 400},
}


@dataclass
class MaterialBuckets:
    """Leaf materials grouped by sourcing category."""

    minerals: Dict[str, int] = field(default_factory=dict)
    pi_p0: Dict[str, int] = field(default_factory=dict)
    pi_other: Dict[str, int] = field(default_factory=dict)
    ice: Dict[str, int] = field(default_factory=dict)
    other: Dict[str, int] = field(default_factory=dict)


@dataclass
class CompressedOrePlan:
    """Reverse-engineered import plan using compressed ore where possible."""

    refine_rate: float = DEFAULT_REFINE_RATE
    # Corp tax on estimated reprocessing output value (e.g. 0.025 = 2.5%).
    # Only set when the plan includes compressed ore that will be reprocessed.
    reprocessing_tax: float = 0.0
    moon_ore_compressed: Dict[str, int] = field(default_factory=dict)
    belt_ore_compressed: Dict[str, int] = field(default_factory=dict)
    mineral_imports: Dict[str, int] = field(default_factory=dict)
    pi_other_imports: Dict[str, int] = field(default_factory=dict)
    ice_imports: Dict[str, int] = field(default_factory=dict)
    other_imports: Dict[str, int] = field(default_factory=dict)
    moon_mineral_byproducts: Dict[str, int] = field(default_factory=dict)
    # Expected minerals from reprocessing the compressed ore (portion-aware).
    expected_minerals: Dict[str, int] = field(default_factory=dict)
    # Leaf mineral needs used for the conversion (for reconciliation).
    mineral_needs: Dict[str, int] = field(default_factory=dict)
    # expected - need (positive = surplus from ore refine).
    mineral_delta: Dict[str, int] = field(default_factory=dict)

    @property
    def includes_compressed_ore(self) -> bool:
        """True when belt/moon ore will be reprocessed at the facility."""
        return bool(self.moon_ore_compressed) or bool(self.belt_ore_compressed)

    def tax_isk(self, output_value: float) -> int:
        """
        ISK fee for reprocessing materials worth ``output_value``.

        Zero when the plan has no compressed ore (nothing to reprocess).
        """
        if (
            not self.includes_compressed_ore
            or output_value <= 0
            or self.reprocessing_tax <= 0
        ):
            return 0
        return math.floor(output_value * self.reprocessing_tax)

    def import_lines(self) -> List[Tuple[str, int]]:
        """Flat freighter list: compressed ore + items bought as-is."""
        lines: Dict[str, int] = {}
        for bucket in (
            self.moon_ore_compressed,
            self.belt_ore_compressed,
            self.mineral_imports,
            self.pi_other_imports,
            self.ice_imports,
            self.other_imports,
        ):
            for name, qty in bucket.items():
                if qty > 0:
                    lines[name] = lines.get(name, 0) + qty
        return sorted(lines.items(), key=lambda item: item[0].lower())

    def multibuy(self) -> str:
        """EVE Online Multibuy paste format: ``Name Quantity`` per line."""
        rows = [f"{name} {qty}" for name, qty in self.import_lines()]
        return "\r\n".join(rows)

    def tsv(self) -> str:
        """Alias for Multibuy paste (kept for existing call sites)."""
        return self.multibuy()


def compression_covered_materials() -> List[str]:
    """Sorted names of materials currently included in compression math."""
    return sorted(COMPRESSION_COVERED_MINERALS | COMPRESSION_COVERED_OTHER)


def compressed_type_name(ore_name: str) -> str:
    if ore_name.startswith("Compressed "):
        return ore_name
    return f"Compressed {ore_name}"


def base_ore_name(compressed_or_base: str) -> str:
    if compressed_or_base.startswith("Compressed "):
        return compressed_or_base[len("Compressed ") :]
    return compressed_or_base


def marketable_compressed_names(ore_names: Sequence[str]) -> List[str]:
    """
    Filter ore base names to those whose Compressed form has average_price > 0.

    If no EveMarketPrice rows exist for any candidate, return all names unchanged
    (offline / empty test DBs).
    """
    compressed_names = [compressed_type_name(n) for n in ore_names]
    priced = set(
        EveMarketPrice.objects.filter(
            eve_type__name__in=compressed_names,
            average_price__gt=0,
        ).values_list("eve_type__name", flat=True)
    )
    if not priced:
        # No market data at all for this set — do not block planning.
        any_prices = EveMarketPrice.objects.filter(
            average_price__gt=0
        ).exists()
        if not any_prices:
            return list(ore_names)
        # Market data exists but these Compressed types are absent → skip them.
        return []
    return [base_ore_name(name) for name in compressed_names if name in priced]


def _ensure_type_materials_loaded(eve_type_id: int) -> None:
    EveType.objects.get_or_create_esi(
        id=eve_type_id,
        enabled_sections=[EveType.Section.TYPE_MATERIALS],
    )


def ore_materials_per_portion(ore_name: str) -> Dict[str, float]:
    """
    Base reprocessing outputs per portion (usually 100 units), at 100% yield.

    Prefers TypeMaterials on the base (uncompressed) ore because Compressed *
    rows are often empty in local SDE mirrors. Falls back to static maps.
    """
    base = base_ore_name(ore_name)
    for candidate in (base, compressed_type_name(base)):
        ore = EveType.objects.filter(name=candidate).first()
        if ore is None:
            continue
        try:
            _ensure_type_materials_loaded(ore.id)
        except Exception:
            pass
        yields: Dict[str, float] = {}
        for material in EveTypeMaterial.objects.filter(
            eve_type_id=ore.id
        ).select_related("material_eve_type"):
            mat_name = material.material_eve_type.name
            if mat_name in MINERAL_NAMES or mat_name in PI_P0_NAMES:
                yields[mat_name] = float(material.quantity)
        if yields:
            return yields

    if base in FALLBACK_BELT_ORE_YIELDS_PER_100:
        return dict(FALLBACK_BELT_ORE_YIELDS_PER_100[base])
    if base in FALLBACK_MOON_YIELDS_PER_100:
        return dict(FALLBACK_MOON_YIELDS_PER_100[base])
    # ore_yield_map is per 1000 m³; HS moon ores are 10 m³/unit → ÷10 = per 100.
    if base in ore_yield_map:
        return {k: float(v) for k, v in ore_yield_map[base].items() if v}
    return {}


def ore_reprocessing_yields(
    ore_name: str,
    refine_rate: float = DEFAULT_REFINE_RATE,
) -> Dict[str, float]:
    """Material yields per 1 ore unit at ``refine_rate``."""
    if refine_rate <= 0:
        raise ValueError("refine_rate must be positive")
    per_portion = ore_materials_per_portion(ore_name)
    return {
        name: (qty / ORE_BATCH_SIZE) * refine_rate
        for name, qty in per_portion.items()
        if qty > 0
    }


def reprocess_output(
    ore_name: str,
    quantity: int,
    refine_rate: float = DEFAULT_REFINE_RATE,
) -> Dict[str, int]:
    """
    Portion-aware refine output: floor(qty / 100 * base * refine_rate).

    Matches in-game batch reprocessing for Compressed / uncompressed ore.
    """
    if quantity <= 0 or refine_rate <= 0:
        return {}
    per_portion = ore_materials_per_portion(ore_name)
    out: Dict[str, int] = {}
    for name, base_qty in per_portion.items():
        produced = math.floor(
            quantity / ORE_BATCH_SIZE * base_qty * refine_rate
        )
        if produced > 0:
            out[name] = produced
    return out


def base_belt_ore_yields(
    refine_rate: float = DEFAULT_REFINE_RATE,
    *,
    require_market: bool = True,
) -> Dict[str, Dict[str, float]]:
    """Per-unit mineral yields for marketable belt ores at refine_rate."""
    candidates = list(BASE_BELT_ORES)
    if require_market:
        marketable = marketable_compressed_names(candidates)
        candidates = marketable if marketable else list(BASE_BELT_ORES)
    loaded: Dict[str, Dict[str, float]] = {}
    for ore_name in candidates:
        yields = ore_reprocessing_yields(ore_name, refine_rate=refine_rate)
        if yields:
            loaded[ore_name] = {
                k: v for k, v in yields.items() if k in MINERAL_NAMES
            }
    return loaded


def categorize_materials(
    materials: Dict[str, int] | Dict[int, int],
) -> MaterialBuckets:
    """
    Split a name→qty or type_id→qty map into minerals / PI / ice / other.
    """
    buckets = MaterialBuckets()
    if not materials:
        return buckets

    named: Dict[str, int] = {}
    int_keys = [k for k in materials if isinstance(k, int)]
    str_keys = [k for k in materials if isinstance(k, str)]
    if int_keys:
        types = {t.id: t.name for t in EveType.objects.filter(id__in=int_keys)}
        for tid in int_keys:
            name = types.get(tid)
            qty = int(materials[tid])
            if name and qty > 0:
                named[name] = named.get(name, 0) + qty
    for name in str_keys:
        qty = int(materials[name])
        if qty > 0:
            named[name] = named.get(name, 0) + qty

    type_by_name = {
        t.name: t
        for t in EveType.objects.filter(name__in=named.keys()).select_related(
            "eve_group"
        )
    }

    for name, qty in named.items():
        if name in MINERAL_NAMES:
            buckets.minerals[name] = buckets.minerals.get(name, 0) + qty
        elif name in PI_P0_NAMES:
            buckets.pi_p0[name] = buckets.pi_p0.get(name, 0) + qty
        elif name in ICE_NAMES:
            buckets.ice[name] = buckets.ice.get(name, 0) + qty
        elif _is_planetary_commodity(name, type_by_name.get(name)):
            buckets.pi_other[name] = buckets.pi_other.get(name, 0) + qty
        else:
            buckets.other[name] = buckets.other.get(name, 0) + qty
    return buckets


def _is_planetary_commodity(name: str, eve_type: Optional[EveType]) -> bool:
    if eve_type is not None:
        group_name = (
            getattr(getattr(eve_type, "eve_group", None), "name", "") or ""
        )
        if "Planet" in group_name or "Commodit" in group_name:
            return True
    pi_keywords = (
        "Fuel Block",
        "Mechanical Parts",
        "Enriched Uranium",
        "Coolant",
        "Robotics",
        "Nanites",
        "Supertensile",
        "Test Cultures",
        "Viral Agent",
        "Chiral Structures",
        "Construction Blocks",
        "Oxygen",
        "Water",
    )
    return any(keyword in name for keyword in pi_keywords)


def moon_ore_for_pi_p0(
    pi_p0_needs: Dict[str, int],
    refine_rate: float = DEFAULT_REFINE_RATE,
    *,
    require_market: bool = True,
) -> Tuple[Dict[str, int], Dict[str, int]]:
    """
    Uncompressed moon ore **units** and mineral byproducts for PI P0 needs.

    Uses per-unit yields (TypeMaterials / fallback). Compressed qty is 1:1.
    """
    if refine_rate <= 0:
        raise ValueError("refine_rate must be positive")

    candidates = list(HIGHSEC_MOON_ORES.keys())
    if require_market:
        marketable = marketable_compressed_names(candidates)
        candidates = (
            marketable if marketable else list(HIGHSEC_MOON_ORES.keys())
        )

    moon_ore_units: Dict[str, int] = {}
    byproducts: Dict[str, int] = {"Pyerite": 0, "Mexallon": 0}

    for ore_name in candidates:
        p0_name = HIGHSEC_MOON_ORES[ore_name]
        need = pi_p0_needs.get(p0_name, 0)
        if need <= 0:
            continue
        yields = ore_reprocessing_yields(ore_name, refine_rate=refine_rate)
        p0_yield = yields.get(p0_name, 0.0)
        if p0_yield <= 0:
            continue
        units = int(math.ceil(need / p0_yield))
        moon_ore_units[ore_name] = moon_ore_units.get(ore_name, 0) + units
        for mineral in ("Pyerite", "Mexallon"):
            mineral_yield = yields.get(mineral, 0.0)
            if mineral_yield:
                byproducts[mineral] += int(math.floor(units * mineral_yield))

    return moon_ore_units, byproducts


def compressed_volume_m3(ore_name: str) -> float:
    """m³ per Compressed unit; unknown ores treated as equal (1.0) for ranking."""
    return COMPRESSED_ORE_VOLUME_M3.get(base_ore_name(ore_name), 1.0)


def mineral_density(
    ore_name: str,
    mineral: str,
    ore_yields: Dict[str, Dict[str, float]],
) -> float:
    """Mineral units per compressed m³ at the yields in ``ore_yields``."""
    per_unit = ore_yields.get(ore_name, {}).get(mineral, 0.0)
    if per_unit <= 0:
        return 0.0
    return per_unit / compressed_volume_m3(ore_name)


def best_belt_ore_for_mineral(
    mineral: str,
    ore_yields: Dict[str, Dict[str, float]],
) -> Optional[str]:
    """
    Pick the allowlisted belt ore with the highest mineral yield per m³.

    Ties break toward PRIMARY_BELT_ORE_FOR_MINERAL, then name.
    """
    candidates = [
        ore
        for ore, yields in ore_yields.items()
        if yields.get(mineral, 0.0) > 0
    ]
    if not candidates:
        return None
    preferred = PRIMARY_BELT_ORE_FOR_MINERAL.get(mineral)
    candidates.sort(
        key=lambda ore: (
            -mineral_density(ore, mineral, ore_yields),
            0 if ore == preferred else 1,
            ore,
        )
    )
    return candidates[0]


def belt_ore_compressed_volume_m3(belt_ore_units: Dict[str, float]) -> float:
    """Total freighter m³ for a belt ore unit map (pre-compression ceil)."""
    return sum(
        max(0.0, float(units)) * compressed_volume_m3(ore)
        for ore, units in belt_ore_units.items()
    )


def _credit_ore_byproducts(
    remaining: Dict[str, float],
    ore_yields: Dict[str, Dict[str, float]],
    ore: str,
    units: float,
    primary: str,
) -> None:
    for mat, mat_yield in ore_yields[ore].items():
        if mat == primary or mat_yield <= 0 or mat not in remaining:
            continue
        remaining[mat] = max(0.0, remaining[mat] - mat_yield * units)


def _pick_preferred_or_best_ore(
    mineral: str,
    ore_yields: Dict[str, Dict[str, float]],
    *,
    exclude: frozenset[str] = frozenset(),
) -> Optional[str]:
    preferred = PRIMARY_BELT_ORE_FOR_MINERAL.get(mineral)
    if (
        preferred
        and preferred not in exclude
        and preferred in ore_yields
        and ore_yields[preferred].get(mineral, 0.0) > 0
    ):
        return preferred
    candidates = {
        name: yields
        for name, yields in ore_yields.items()
        if name not in exclude
    }
    return best_belt_ore_for_mineral(mineral, candidates)


def _cover_mineral_with_belt_ore(
    remaining: Dict[str, float],
    belt_ore: Dict[str, float],
    ore_yields: Dict[str, Dict[str, float]],
    mineral: str,
    *,
    exclude: frozenset[str] = frozenset(),
    credit_byproducts: bool = True,
) -> None:
    """Size ore for one mineral; optionally credit byproducts to remaining."""
    if remaining.get(mineral, 0) <= 0:
        return
    if mineral not in COMPRESSION_COVERED_MINERALS:
        return
    ore = _pick_preferred_or_best_ore(mineral, ore_yields, exclude=exclude)
    ore_yield = ore_yields.get(ore, {}).get(mineral, 0.0) if ore else 0.0
    if not ore or ore_yield <= 0:
        return
    units = remaining[mineral] / ore_yield
    belt_ore[ore] = belt_ore.get(ore, 0.0) + units
    remaining[mineral] = 0.0
    if credit_byproducts:
        _credit_ore_byproducts(remaining, ore_yields, ore, units, mineral)


def _tritanium_ore_excludes() -> frozenset[str]:
    """Exclude Pye/Mex ores so Trit never inflates those stacks."""
    mex_ores = {
        PRIMARY_BELT_ORE_FOR_MINERAL.get("Mexallon"),
        "Plagioclase",
        "Pyroxeres",
        "Kernite",
    }
    return _PYE_ORES | {o for o in mex_ores if o}


def compute_practical_belt_blend(
    mineral_needs: Dict[str, int],
    moon_byproducts: Dict[str, int],
    ore_yields: Dict[str, Dict[str, float]],
) -> Tuple[Dict[str, float], Dict[str, int]]:
    """
    Uncompressed ore units for allowlisted minerals after moon credit.

    Selection (isolation-optimal; order matters for byproduct credit):
    1. Cover Pyerite with densest Pye ore (Zeolites; Scordite fallback).
       Size strictly for Pye — never chase Trit/Mex with this ore.
    2. Credit all mineral byproducts from step 1 against remaining needs.
    3. Cover remaining Mexallon with Plagioclase (Pyroxeres/Kernite fallback).
       Never size Zeolites/Scordite for Mex. Credit Trit (and other) byproducts.
    4. Cover remaining Tritanium with Veldspar only.

    Minerals outside COMPRESSION_COVERED_MINERALS always stay as imports
    (e.g. Isogen from Kernite fallback may reduce an Iso import line).
    """
    remaining = {
        mineral: float(
            max(
                0,
                mineral_needs.get(mineral, 0)
                - moon_byproducts.get(mineral, 0),
            )
        )
        for mineral in MINERAL_NAMES
    }
    belt_ore: Dict[str, float] = {}

    # Pyerite: Zeolites (or densest available Pye ore).
    _cover_mineral_with_belt_ore(remaining, belt_ore, ore_yields, "Pyerite")
    # Mexallon: Plagioclase — never size Pye-ores for Mex.
    _cover_mineral_with_belt_ore(
        remaining,
        belt_ore,
        ore_yields,
        "Mexallon",
        exclude=_PYE_ORES,
    )
    # Tritanium: Veldspar only — never size Pye/Mex ore to fill Trit.
    _cover_mineral_with_belt_ore(
        remaining,
        belt_ore,
        ore_yields,
        "Tritanium",
        exclude=_tritanium_ore_excludes(),
        credit_byproducts=False,
    )

    mineral_imports: Dict[str, int] = {}
    for mineral, qty in remaining.items():
        if qty <= 0:
            continue
        mineral_imports[mineral] = int(math.ceil(qty))
    return belt_ore, mineral_imports


def to_compressed_units(
    uncompressed_units: Dict[str, float],
) -> Dict[str, int]:
    """
    Convert ore units to Compressed stacks.

    Modern compression is 1:1 quantity (volume shrinks ~100×).
    """
    compressed: Dict[str, int] = {}
    for ore_name, units in uncompressed_units.items():
        if units <= 0:
            continue
        name = compressed_type_name(ore_name)
        compressed[name] = compressed.get(name, 0) + int(math.ceil(units))
    return compressed


def _sum_reprocess_outputs(
    compressed: Dict[str, int],
    refine_rate: float,
) -> Dict[str, int]:
    totals: Dict[str, int] = {}
    for name, qty in compressed.items():
        for mat, produced in reprocess_output(
            base_ore_name(name), qty, refine_rate=refine_rate
        ).items():
            totals[mat] = totals.get(mat, 0) + produced
    return totals


def conservative_refine_rate(refine_rate: float) -> float:
    """
    Yield used for shopping-list coverage checks.

    UI shows refine as ``(rate * 100).toFixed(2)``; Janice users typically
    enter that rounded percent. Never use a rate above the true facility
    yield (rounding can bump 85.775% → 85.78%).
    """
    if refine_rate <= 0:
        return refine_rate
    # Round via hundredths-of-a-percent integers to avoid 0.8576999999999999.
    display = round(refine_rate * 10000) / 10000.0
    return min(display, refine_rate)


def _top_up_floor_coverage(
    belt_compressed: Dict[str, int],
    mineral_needs: Dict[str, int],
    mineral_imports: Dict[str, int],
    refine_rate: float,
    *,
    max_iterations: int = 100_000,
) -> None:
    """
    Add primary belt ore until floored reprocess meets covered mineral needs.

    Coverage is checked at ``conservative_refine_rate`` (UI/Janice 2-dp
    percent) so shopping lists still cover after portion flooring when
    validated at the displayed yield. Continuous blend sizing alone can
    undershoot by a few units at full precision, or by more when the
    displayed rate is slightly below the true facility rate.
    """
    coverage_rate = conservative_refine_rate(refine_rate)
    for _ in range(max_iterations):
        expected = _sum_reprocess_outputs(belt_compressed, coverage_rate)
        shortfall: Optional[str] = None
        shortfall_qty = 0
        for mineral in COMPRESSION_COVERED_MINERALS:
            need = mineral_needs.get(mineral, 0)
            got = expected.get(mineral, 0) + mineral_imports.get(mineral, 0)
            if got < need:
                shortfall = mineral
                shortfall_qty = need - got
                break
        if shortfall is None:
            return
        ore = PRIMARY_BELT_ORE_FOR_MINERAL.get(shortfall)
        if not ore:
            return
        name = compressed_type_name(ore)
        base_qty = ore_materials_per_portion(ore).get(shortfall, 0.0)
        yield_per = (base_qty / ORE_BATCH_SIZE) * coverage_rate
        if yield_per <= 0:
            return
        add = max(1, math.ceil(shortfall_qty / yield_per))
        belt_compressed[name] = belt_compressed.get(name, 0) + add


def _mineral_delta(
    needs: Dict[str, int],
    expected: Dict[str, int],
    imports: Dict[str, int],
) -> Dict[str, int]:
    """expected + refined imports - needs (per mineral)."""
    names = set(needs) | set(expected) | set(imports)
    delta: Dict[str, int] = {}
    for name in names:
        if name not in MINERAL_NAMES:
            continue
        delta[name] = (
            expected.get(name, 0) + imports.get(name, 0) - needs.get(name, 0)
        )
    return {k: v for k, v in sorted(delta.items()) if v != 0 or k in needs}


def build_compressed_ore_plan(
    materials: Dict[str, int] | Dict[int, int] | MaterialBuckets,
    refine_rate: float = DEFAULT_REFINE_RATE,
    use_moon_ore: bool = True,
    reprocessing_tax: float = 0.0,
    require_market: bool = True,
) -> CompressedOrePlan:
    """
    Reverse leaf materials into compressed moon/belt ore plus direct imports.

    ``require_market`` limits Compressed types to those with EveMarketPrice > 0
    when any market prices are present in the DB.
    """
    if isinstance(materials, MaterialBuckets):
        buckets = materials
    else:
        buckets = categorize_materials(materials)

    plan = CompressedOrePlan(
        refine_rate=refine_rate,
        reprocessing_tax=reprocessing_tax,
        mineral_needs=dict(buckets.minerals),
    )
    mineral_needs = dict(buckets.minerals)
    pi_p0_needs = dict(buckets.pi_p0)

    moon_byproducts: Dict[str, int] = {}
    pi_covered_by_compression = bool(COMPRESSION_COVERED_OTHER & PI_P0_NAMES)
    if use_moon_ore and pi_p0_needs and pi_covered_by_compression:
        moon_units, moon_byproducts = moon_ore_for_pi_p0(
            {
                name: qty
                for name, qty in pi_p0_needs.items()
                if name in COMPRESSION_COVERED_OTHER
            },
            refine_rate=refine_rate,
            require_market=require_market,
        )
        plan.moon_ore_compressed = to_compressed_units(
            {k: float(v) for k, v in moon_units.items()}
        )
        plan.moon_mineral_byproducts = moon_byproducts
        # Uncovered PI P0 (not allowlisted / no marketable moon ore) stays import.
        covered = {
            HIGHSEC_MOON_ORES[base_ore_name(n)]
            for n in plan.moon_ore_compressed
        }
        for p0_name, qty in pi_p0_needs.items():
            if p0_name not in covered and qty > 0:
                plan.other_imports[p0_name] = (
                    plan.other_imports.get(p0_name, 0) + qty
                )
    elif pi_p0_needs:
        plan.other_imports.update(pi_p0_needs)

    ore_yields = base_belt_ore_yields(
        refine_rate=refine_rate, require_market=require_market
    )
    belt_units, mineral_imports = compute_practical_belt_blend(
        mineral_needs, moon_byproducts, ore_yields
    )
    plan.belt_ore_compressed = to_compressed_units(belt_units)
    _top_up_floor_coverage(
        plan.belt_ore_compressed,
        mineral_needs,
        mineral_imports,
        refine_rate,
    )
    plan.mineral_imports = mineral_imports
    plan.pi_other_imports.update(buckets.pi_other)
    plan.ice_imports.update(buckets.ice)
    plan.other_imports.update(buckets.other)

    # Expected / delta at the true facility rate (in-game). Top-up used the
    # conservative display rate, so these deltas are typically a small surplus.
    plan.expected_minerals = _sum_reprocess_outputs(
        {**plan.moon_ore_compressed, **plan.belt_ore_compressed},
        refine_rate,
    )
    # Expected minerals from ore only (PI P0 counted separately in moon refine).
    plan.mineral_delta = _mineral_delta(
        mineral_needs, plan.expected_minerals, mineral_imports
    )

    if not plan.includes_compressed_ore:
        plan.reprocessing_tax = 0.0
    return plan
