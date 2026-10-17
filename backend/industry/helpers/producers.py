"""
Characters and corporations dealing with a product type.

character_producers: primary character per user with total_value_isk (industry jobs,
    planetary output, and mining merged into one list per product type).
corporation_producers: corporations with industry jobs (total_value_isk).
"""

from decimal import Decimal
from datetime import timedelta

from django.db.models import Q, Sum
from django.utils import timezone

from eveuniverse.models import (
    EveIndustryActivityProduct,
    EveMarketPrice,
    EveTypeMaterial,
)

from eveonline.models import (
    EveCharacterIndustryJob,
    EveCharacterMiningEntry,
    EveCharacterPlanetOutput,
    EveCorporationIndustryJob,
)
from eveonline.helpers.characters.identity import (
    primary_characters_for_characters,
)

ACTIVITY_MANUFACTURING = 1
ACTIVITY_REACTION = 11
PRODUCTION_ACTIVITIES = (ACTIVITY_MANUFACTURING, ACTIVITY_REACTION)

ORE_MINERAL_SHARE_THRESHOLD = 0.25

# Default reprocessing yield (84%) for valuing mined ore → mineral output
DEFAULT_REFINE_RATE = 0.84
# SDE type material quantities are per 100 units of ore (batch), not per 1 unit
ORE_BATCH_SIZE = 100

# Rolling window and minimum value for PI and mining producers on industry products
PI_ROLLING_DAYS = 30
MINING_WINDOW_DAYS = 30
MIN_PI_MINING_VALUE_ISK = 50_000_000
# Only include PI from planets synced within the last N days
PI_PLANET_MAX_AGE_DAYS = 30


def _get_material_prices(type_ids: list[int]) -> dict[int, float]:
    """Return average_price for each type_id from EveMarketPrice; missing types are omitted."""
    if not type_ids:
        return {}
    return dict(
        EveMarketPrice.objects.filter(eve_type_id__in=type_ids).values_list(
            "eve_type_id", "average_price"
        )
    )


def _resolve_to_primary_producers(character_refs):
    """
    Map each producing character to their user's primary character; dedupe by primary.
    Returns list of {"id": character_id, "name": character_name, "total_value_isk": float}.
    total_value_isk is summed when merging to the same primary. Characters without
    a linked user/primary are left as-is.
    """
    if not character_refs:
        return []
    primaries = primary_characters_for_characters(
        c["id"] for c in character_refs
    )
    # primary_id -> (name, total_value_isk)
    merged: dict[int, tuple[str, float]] = {}
    for ref in character_refs:
        cid = ref["id"]
        cname = ref["name"] or ""
        value = ref.get("total_value_isk") or 0.0
        primary = primaries.get(cid)
        if primary:
            pid, pname = primary.character_id, primary.character_name or ""
            if pid not in merged:
                merged[pid] = (pname, value)
            else:
                old_name, old_val = merged[pid]
                merged[pid] = (old_name, old_val + value)
        else:
            if cid not in merged:
                merged[cid] = (cname, value)
            else:
                old_name, old_val = merged[cid]
                merged[cid] = (old_name, old_val + value)
    return [
        {"id": pid, "name": name, "total_value_isk": round(val, 2)}
        for pid, (name, val) in merged.items()
    ]


def blueprint_activity_pairs_for_product_type(product_type_id: int):
    """(blueprint_type_id, activity_id) pairs that produce this product type."""
    return set(
        EveIndustryActivityProduct.objects.filter(
            product_eve_type_id=product_type_id,
            activity_id__in=PRODUCTION_ACTIVITIES,
        ).values_list("eve_type_id", "activity_id")
    )


def _build_blueprint_activity_to_types(type_ids):
    """Map (blueprint_type_id, activity_id) -> list of product_eve_type_id."""
    rows = EveIndustryActivityProduct.objects.filter(
        product_eve_type_id__in=type_ids,
        activity_id__in=PRODUCTION_ACTIVITIES,
    ).values_list("eve_type_id", "activity_id", "product_eve_type_id")
    out = {}
    for bid, aid, tid in rows:
        key = (bid, aid)
        if key not in out:
            out[key] = []
        out[key].append(tid)
    return out


def _build_blueprint_activity_quantity(type_ids):
    """Map (blueprint_type_id, activity_id) -> { product_eve_type_id: quantity_per_run }."""
    rows = EveIndustryActivityProduct.objects.filter(
        product_eve_type_id__in=type_ids,
        activity_id__in=PRODUCTION_ACTIVITIES,
    ).values_list(
        "eve_type_id", "activity_id", "product_eve_type_id", "quantity"
    )
    out = {}
    for bid, aid, tid, qty in rows:
        key = (bid, aid)
        if key not in out:
            out[key] = {}
        out[key][tid] = qty if qty is not None else 1
    return out


def _fill_job_producers(result, type_ids, blueprint_activity_to_types):
    """Populate character_producers and corporation_producers from industry jobs with total_value_isk."""
    q = Q()
    for (bid, aid), _ in blueprint_activity_to_types.items():
        q |= Q(blueprint_type_id=bid, activity_id=aid)
    prices = _get_material_prices(type_ids)
    activity_quantity = _build_blueprint_activity_quantity(type_ids)

    char_jobs = (
        EveCharacterIndustryJob.objects.filter(q)
        .select_related("character")
        .values_list(
            "blueprint_type_id",
            "activity_id",
            "runs",
            "character__character_id",
            "character__character_name",
        )
    )
    corp_jobs = (
        EveCorporationIndustryJob.objects.filter(q)
        .select_related("corporation")
        .values_list(
            "blueprint_type_id",
            "activity_id",
            "runs",
            "corporation__corporation_id",
            "corporation__name",
        )
    )

    # (tid, cid) -> (name, total_value_isk)
    char_value: dict[tuple[int, int], tuple[str, float]] = {}
    for bid, aid, runs, cid, cname in char_jobs:
        qty_per_tid = activity_quantity.get((bid, aid), {})
        for tid in blueprint_activity_to_types.get((bid, aid), []):
            qty_per_run = qty_per_tid.get(tid, 1)
            price = float(prices.get(tid) or 0)
            value = runs * qty_per_run * price
            key = (tid, cid)
            if key not in char_value:
                char_value[key] = (cname or "", value)
            else:
                old_name, old_val = char_value[key]
                char_value[key] = (old_name, old_val + value)

    corp_value: dict[tuple[int, int], tuple[str, float]] = {}
    for bid, aid, runs, cid, cname in corp_jobs:
        qty_per_tid = activity_quantity.get((bid, aid), {})
        for tid in blueprint_activity_to_types.get((bid, aid), []):
            qty_per_run = qty_per_tid.get(tid, 1)
            price = float(prices.get(tid) or 0)
            value = runs * qty_per_run * price
            key = (tid, cid)
            if key not in corp_value:
                corp_value[key] = (cname or "", value)
            else:
                old_name, old_val = corp_value[key]
                corp_value[key] = (old_name, old_val + value)

    for tid in type_ids:
        result[tid]["character_producers"] = [
            {"id": cid, "name": name, "total_value_isk": round(val, 2)}
            for (t, cid), (name, val) in char_value.items()
            if t == tid
        ]
        result[tid]["corporation_producers"] = [
            {"id": cid, "name": name, "total_value_isk": round(val, 2)}
            for (t, cid), (name, val) in corp_value.items()
            if t == tid
        ]


def _fill_planetary_producers(result, type_ids):
    """
    Add planetary output value to character_producers.

    Uses rolling 30-day value: sum(daily_quantity) * PI_ROLLING_DAYS * price per
    character. Only includes outputs from planets synced in the last
    PI_PLANET_MAX_AGE_DAYS (30). Only adds a character from PI if their PI value
    is at least MIN_PI_MINING_VALUE_ISK (50M); when merging into existing (e.g.
    from jobs) the value is added regardless.
    """
    planet_cutoff = timezone.now() - timedelta(days=PI_PLANET_MAX_AGE_DAYS)
    planet_outputs = (
        EveCharacterPlanetOutput.objects.filter(
            eve_type_id__in=type_ids,
            planet__last_update__isnull=False,
            planet__last_update__gte=planet_cutoff,
        )
        .values(
            "eve_type_id",
            "planet__character__character_id",
            "planet__character__character_name",
        )
        .annotate(total_daily=Sum("daily_quantity"))
    )
    # (tid, cid) -> (name, total_daily_quantity)
    char_pi: dict[int, dict[int, tuple[str, Decimal]]] = {
        tid: {} for tid in type_ids
    }
    for row in planet_outputs:
        tid = row["eve_type_id"]
        cid = row["planet__character__character_id"]
        cname = row["planet__character__character_name"] or ""
        total_daily = row["total_daily"] or Decimal(0)
        if tid not in char_pi:
            continue
        if cid not in char_pi[tid]:
            char_pi[tid][cid] = (cname, total_daily)
        else:
            name, daily = char_pi[tid][cid]
            char_pi[tid][cid] = (name, daily + total_daily)
    prices = _get_material_prices(type_ids)
    for tid in type_ids:
        price = float(prices.get(tid) or 0)
        existing_ids = {c["id"] for c in result[tid]["character_producers"]}
        for cid, (cname, total_daily) in char_pi.get(tid, {}).items():
            quantity_30d = float(total_daily) * PI_ROLLING_DAYS
            value = round(quantity_30d * price, 2)
            if cid in existing_ids:
                for entry in result[tid]["character_producers"]:
                    if entry["id"] == cid:
                        entry["total_value_isk"] += value
                        break
            elif value >= MIN_PI_MINING_VALUE_ISK:
                existing_ids.add(cid)
                result[tid]["character_producers"].append(
                    {"id": cid, "name": cname, "total_value_isk": value}
                )


def get_producers_for_types(product_type_ids):
    """
    Batch: for each product type_id, return character_producers and
    corporation_producers. Character producers aggregate industry jobs,
    planetary output, and mining (one list per type, total_value_isk summed).
    """
    if not product_type_ids:
        return {}
    type_ids = list(product_type_ids)
    result = {
        tid: {
            "character_producers": [],
            "corporation_producers": [],
        }
        for tid in type_ids
    }
    blueprint_activity_to_types = _build_blueprint_activity_to_types(type_ids)
    if blueprint_activity_to_types:
        _fill_job_producers(result, type_ids, blueprint_activity_to_types)
    _fill_planetary_producers(result, type_ids)
    _fill_mining_producers(result, type_ids)
    for tid in type_ids:
        result[tid]["character_producers"].sort(
            key=lambda c: c["total_value_isk"], reverse=True
        )
        result[tid]["character_producers"] = _resolve_to_primary_producers(
            result[tid]["character_producers"]
        )
        result[tid]["character_producers"].sort(
            key=lambda c: c["total_value_isk"], reverse=True
        )
    return result


# ---------------------------------------------------------------------------
# Mining producers
# ---------------------------------------------------------------------------


def _get_ore_yield_per_unit(
    material_to_products: dict[int, list[int]],
) -> dict[tuple[int, int], float]:
    """
    Return (ore_tid, product_tid) -> mineral units per unit ore (at 100% refine).
    SDE quantities are per batch of ORE_BATCH_SIZE (100) ore, so we divide by
    ORE_BATCH_SIZE. Direct ore (product is the ore itself) = 1.0.
    Value = qty * yield_per_unit * refine_rate * price.
    """
    if not material_to_products:
        return {}
    out: dict[tuple[int, int], float] = {}
    for ore_tid, product_tids in material_to_products.items():
        for product_tid in product_tids:
            if ore_tid == product_tid:
                out[(ore_tid, product_tid)] = 1.0
            else:
                qty = (
                    EveTypeMaterial.objects.filter(
                        eve_type_id=ore_tid,
                        material_eve_type_id=product_tid,
                    )
                    .values_list("quantity", flat=True)
                    .first()
                    or 0
                )
                # SDE quantity is per 100 units of ore
                out[(ore_tid, product_tid)] = float(qty) / ORE_BATCH_SIZE
    return out


def _build_ore_to_materials_above_threshold(type_ids):
    """
    Build ore_tid -> [material_tid] only for materials that make up at least
    ORE_MINERAL_SHARE_THRESHOLD of that ore's total output. Uses value share
    (quantity * price) when EveMarketPrice exists, else volume share.
    """
    ore_source_rows = list(
        EveTypeMaterial.objects.filter(
            material_eve_type_id__in=type_ids,
        ).values_list("eve_type_id", "material_eve_type_id", "quantity")
    )
    if not ore_source_rows:
        return {}
    ore_ids = list({r[0] for r in ore_source_rows})
    # Volume totals (fallback)
    vol_totals = dict(
        EveTypeMaterial.objects.filter(eve_type_id__in=ore_ids)
        .values("eve_type_id")
        .annotate(total=Sum("quantity"))
        .values_list("eve_type_id", "total")
    )
    # All materials per ore for value calc
    all_ore_mats = list(
        EveTypeMaterial.objects.filter(eve_type_id__in=ore_ids).values_list(
            "eve_type_id", "material_eve_type_id", "quantity"
        )
    )
    mat_ids = list({m[1] for m in all_ore_mats})
    prices = _get_material_prices(mat_ids)
    use_value = len(prices) == len(mat_ids) and all(
        prices.get(m) for m in mat_ids
    )
    if use_value:
        ore_total_value = {}
        for ore_id, mat_id, qty in all_ore_mats:
            ore_total_value[ore_id] = ore_total_value.get(ore_id, 0) + (
                qty * (prices.get(mat_id) or 0)
            )
    material_to_products: dict[int, list[int]] = {}
    for ore_tid, mat_tid, qty in ore_source_rows:
        if mat_tid not in type_ids:
            continue
        if use_value and (ore_total_value.get(ore_tid) or 0) > 0:
            share = (qty * (prices.get(mat_tid) or 0)) / ore_total_value[
                ore_tid
            ]
        else:
            total = vol_totals.get(ore_tid) or 0
            share = (qty / total) if total > 0 else 0
        if share >= ORE_MINERAL_SHARE_THRESHOLD:
            material_to_products.setdefault(ore_tid, []).append(mat_tid)
    return material_to_products


def _fill_mining_producers(result, type_ids):
    """Add mining output value to character_producers (ore/mineral contribution per character)."""
    material_to_products = _build_ore_to_materials_above_threshold(type_ids)
    all_ore_type_ids: set[int] = set(material_to_products.keys())
    for tid in type_ids:
        material_to_products.setdefault(tid, []).append(tid)
    all_ore_type_ids.update(type_ids)

    yield_per_unit = _get_ore_yield_per_unit(material_to_products)
    prices = _get_material_prices(type_ids)

    cutoff = timezone.now().date() - timedelta(days=MINING_WINDOW_DAYS)

    mining_rows = (
        EveCharacterMiningEntry.objects.filter(
            eve_type_id__in=all_ore_type_ids,
            date__gte=cutoff,
        )
        .values(
            "eve_type_id",
            "character__character_id",
            "character__character_name",
        )
        .annotate(total_quantity=Sum("quantity"))
    )

    miner_value: dict[int, dict[int, float]] = {tid: {} for tid in type_ids}
    miner_name: dict[int, str] = {}

    for row in mining_rows:
        ore_tid = row["eve_type_id"]
        cid = row["character__character_id"]
        cname = row["character__character_name"] or ""
        qty = row["total_quantity"]
        miner_name[cid] = cname

        for product_tid in material_to_products.get(ore_tid, []):
            if product_tid not in result:
                continue
            y = yield_per_unit.get((ore_tid, product_tid), 0.0)
            price = float(prices.get(product_tid) or 0)
            refine = DEFAULT_REFINE_RATE if ore_tid != product_tid else 1.0
            value = qty * y * refine * price
            miner_value[product_tid][cid] = (
                miner_value[product_tid].get(cid, 0) + value
            )

    for tid in type_ids:
        existing_ids = {c["id"] for c in result[tid]["character_producers"]}
        for cid, value in miner_value[tid].items():
            value = round(value, 2)
            if cid in existing_ids:
                for entry in result[tid]["character_producers"]:
                    if entry["id"] == cid:
                        entry["total_value_isk"] += value
                        break
            elif value >= MIN_PI_MINING_VALUE_ISK:
                existing_ids.add(cid)
                result[tid]["character_producers"].append(
                    {
                        "id": cid,
                        "name": miner_name.get(cid, ""),
                        "total_value_isk": value,
                    }
                )
