"""
Characters and corporations dealing with a product type.

character_producers: primary character per user with total_value_isk (industry jobs,
    planetary output, and mining merged into one list per product type).
corporation_producers: corporations with industry jobs (total_value_isk).
"""

from datetime import timedelta

from django.db.models import Q, Sum
from django.utils import timezone

from eveuniverse.models import (
    EveIndustryActivityProduct,
    EveMarketPrice,
    EveTypeMaterial,
)

from eveonline.models import (
    EveCharacter,
    EveCharacterIndustryJob,
    EveCharacterMiningEntry,
    EveCharacterPlanetOutput,
    EveCorporationIndustryJob,
)
from eveonline.helpers.characters import character_primary

ACTIVITY_MANUFACTURING = 1
ACTIVITY_REACTION = 11
PRODUCTION_ACTIVITIES = (ACTIVITY_MANUFACTURING, ACTIVITY_REACTION)

ORE_MINERAL_SHARE_THRESHOLD = 0.25


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
    ids = [c["id"] for c in character_refs]
    characters = {
        c.character_id: c
        for c in EveCharacter.objects.filter(character_id__in=ids)
    }
    # primary_id -> (name, total_value_isk)
    merged: dict[int, tuple[str, float]] = {}
    for ref in character_refs:
        cid = ref["id"]
        cname = ref["name"] or ""
        value = ref.get("total_value_isk") or 0.0
        char = characters.get(cid)
        primary = None
        if char:
            try:
                primary = character_primary(char)
            except (AttributeError, TypeError):
                pass
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


def _blueprint_activity_pairs_for_product_type(product_type_id: int):
    """(blueprint_type_id, activity_id) pairs that produce this product type."""
    return set(
        EveIndustryActivityProduct.objects.filter(
            product_eve_type_id=product_type_id,
            activity_id__in=PRODUCTION_ACTIVITIES,
        ).values_list("eve_type_id", "activity_id")
    )


def get_character_producers_for_type(product_type_id: int):
    """
    All characters dealing with this product type (industry jobs and/or planetary
    output), resolved to each user's primary character. Returns list of
    {"id": character_id, "name": character_name}, one per user, distinct.
    """
    seen = set()
    out = []

    # Industry jobs (manufacturing, reactions)
    pairs = _blueprint_activity_pairs_for_product_type(product_type_id)
    if pairs:
        q = Q()
        for blueprint_type_id, activity_id in pairs:
            q |= Q(
                blueprint_type_id=blueprint_type_id, activity_id=activity_id
            )
        jobs = (
            EveCharacterIndustryJob.objects.filter(q)
            .select_related("character")
            .values_list(
                "character__character_id", "character__character_name"
            )
            .distinct()
        )
        for cid, cname in jobs:
            if cid not in seen:
                seen.add(cid)
                out.append({"id": cid, "name": cname or ""})

    # Planetary output
    planet_outputs = (
        EveCharacterPlanetOutput.objects.filter(eve_type_id=product_type_id)
        .select_related("planet__character")
        .values_list(
            "planet__character__character_id",
            "planet__character__character_name",
        )
        .distinct()
    )
    for cid, cname in planet_outputs:
        if cid not in seen:
            seen.add(cid)
            out.append({"id": cid, "name": cname or ""})
    return _resolve_to_primary_producers(out)


def get_corporation_producers_for_type(product_type_id: int):
    """
    Corporations who have industry jobs producing this product type.
    Returns list of {"id": corporation_id, "name": corporation_name}, distinct.
    """
    pairs = _blueprint_activity_pairs_for_product_type(product_type_id)
    if not pairs:
        return []
    q = Q()
    for blueprint_type_id, activity_id in pairs:
        q |= Q(blueprint_type_id=blueprint_type_id, activity_id=activity_id)
    jobs = (
        EveCorporationIndustryJob.objects.filter(q)
        .select_related("corporation")
        .values_list("corporation__corporation_id", "corporation__name")
        .distinct()
    )
    seen = set()
    out = []
    for cid, cname in jobs:
        if cid not in seen:
            seen.add(cid)
            out.append({"id": cid, "name": cname or ""})
    return out


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
    """Add planetary output value to character_producers (PI contribution per character)."""
    planet_outputs = (
        EveCharacterPlanetOutput.objects.filter(eve_type_id__in=type_ids)
        .select_related("planet__character")
        .values_list(
            "eve_type_id",
            "planet__character__character_id",
            "planet__character__character_name",
        )
    )
    # (tid, cid) -> (name, planet_count)
    char_pi: dict[int, dict[int, tuple[str, int]]] = {
        tid: {} for tid in type_ids
    }
    for eve_type_id, cid, cname in planet_outputs:
        if eve_type_id not in char_pi:
            continue
        if cid not in char_pi[eve_type_id]:
            char_pi[eve_type_id][cid] = (cname or "", 1)
        else:
            name, count = char_pi[eve_type_id][cid]
            char_pi[eve_type_id][cid] = (name, count + 1)
    prices = _get_material_prices(type_ids)
    for tid in type_ids:
        price = float(prices.get(tid) or 0)
        existing_ids = {c["id"] for c in result[tid]["character_producers"]}
        for cid, (cname, count) in char_pi.get(tid, {}).items():
            value = round(count * price, 2)
            if cid in existing_ids:
                for entry in result[tid]["character_producers"]:
                    if entry["id"] == cid:
                        entry["total_value_isk"] += value
                        break
            else:
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


def _sort_planetary_by_value(entries, product_type_id: int):
    """Sort PI producers by total ISK value (planet_count * price) descending."""
    if not entries:
        return entries
    char_planet_count: dict[int, int] = {}
    for e in entries:
        cid = e["character_id"]
        char_planet_count[cid] = char_planet_count.get(cid, 0) + 1
    price = float(
        _get_material_prices([product_type_id]).get(product_type_id) or 0
    )
    for e in entries:
        cid = e["character_id"]
        count = char_planet_count[cid]
        e["planet_count"] = count
        e["total_value_isk"] = count * price
    entries.sort(key=lambda x: x["total_value_isk"], reverse=True)
    return entries


def get_planetary_producers_for_type(product_type_id: int):
    """
    Characters whose planetary colonies produce or harvest this type.
    Returns list of dicts with character_id, character_name, planet_id,
    solar_system_id, planet_type, output_type, planet_count.
    Sorted by planet_count descending.
    """
    outputs = (
        EveCharacterPlanetOutput.objects.filter(
            eve_type_id=product_type_id,
        )
        .select_related("planet__character")
        .values_list(
            "output_type",
            "planet__character__character_id",
            "planet__character__character_name",
            "planet__planet_id",
            "planet__solar_system_id",
            "planet__planet_type",
        )
    )
    seen = set()
    out = []
    for output_type, cid, cname, planet_id, system_id, ptype in outputs:
        key = (cid, planet_id)
        if key not in seen:
            seen.add(key)
            out.append(
                {
                    "character_id": cid,
                    "character_name": cname or "",
                    "planet_id": planet_id,
                    "solar_system_id": system_id,
                    "planet_type": ptype or "",
                    "output_type": output_type,
                }
            )
    return _sort_planetary_by_value(out, product_type_id)


# ---------------------------------------------------------------------------
# Mining producers
# ---------------------------------------------------------------------------

MINING_WINDOW_DAYS = 30


def _ore_type_ids_for_material(material_type_id: int) -> set[int]:
    """
    Return type_ids of ores whose reprocessing yields this material and where
    the material makes up at least ORE_MINERAL_SHARE_THRESHOLD (25%) of the ore.

    When EveMarketPrice data exists, share is by value (quantity * price); otherwise
    by volume (quantity). Value weighting makes e.g. Kylixium count as a Mexallon ore.
    """
    rows = list(
        EveTypeMaterial.objects.filter(
            material_eve_type_id=material_type_id,
        ).values_list("eve_type_id", "quantity")
    )
    if not rows:
        return set()
    ore_ids = list({r[0] for r in rows})
    # Volume-based totals (fallback)
    vol_totals = dict(
        EveTypeMaterial.objects.filter(eve_type_id__in=ore_ids)
        .values("eve_type_id")
        .annotate(total=Sum("quantity"))
        .values_list("eve_type_id", "total")
    )
    # Value-based: need all materials per ore and their prices
    ore_materials = list(
        EveTypeMaterial.objects.filter(eve_type_id__in=ore_ids).values_list(
            "eve_type_id", "material_eve_type_id", "quantity"
        )
    )
    mat_ids = list({m[1] for m in ore_materials})
    prices = _get_material_prices(mat_ids)
    use_value = len(prices) == len(mat_ids) and all(
        prices.get(mid) for mid in mat_ids
    )
    if use_value:
        # total value per ore
        ore_total_value: dict[int, float] = {}
        for ore_id, mat_id, qty in ore_materials:
            ore_total_value[ore_id] = ore_total_value.get(ore_id, 0) + (
                qty * (prices.get(mat_id) or 0)
            )
        return {
            ore_id
            for ore_id, qty in rows
            if (ore_total_value.get(ore_id) or 0) > 0
            and (qty * (prices.get(material_type_id) or 0))
            / ore_total_value[ore_id]
            >= ORE_MINERAL_SHARE_THRESHOLD
        }
    # Volume-based
    return {
        ore_id
        for ore_id, qty in rows
        if (vol_totals.get(ore_id) or 0) > 0
        and qty / (vol_totals[ore_id] or 1) >= ORE_MINERAL_SHARE_THRESHOLD
    }


def get_mining_producers_for_type(product_type_id: int):
    """
    Characters who mined ores relevant to this product type in the last 30 days.

    Two lookup paths:
      1. Direct: the product type IS an ore that was mined.
      2. Reprocessing: the product type is a mineral; find ores whose
         EveTypeMaterial rows list it as an output, then find miners of
         those ores.

    Returns list of dicts sorted by total_value_isk descending:
        {"character_id", "character_name", "total_quantity", "total_value_isk"}
    Characters are resolved to their user's primary character.
    """
    ore_type_ids = _ore_type_ids_for_material(product_type_id)
    ore_type_ids.add(product_type_id)

    cutoff = timezone.now().date() - timedelta(days=MINING_WINDOW_DAYS)

    # Rows per (character, eve_type_id) so we can apply yield and price
    rows = (
        EveCharacterMiningEntry.objects.filter(
            eve_type_id__in=ore_type_ids,
            date__gte=cutoff,
        )
        .values(
            "eve_type_id",
            "character__character_id",
            "character__character_name",
        )
        .annotate(total_quantity=Sum("quantity"))
    )

    material_to_products = _build_ore_to_materials_above_threshold(
        [product_type_id]
    )
    material_to_products.setdefault(product_type_id, []).append(
        product_type_id
    )
    yield_frac = _get_ore_yield_fractions(material_to_products)
    price = float(
        _get_material_prices([product_type_id]).get(product_type_id) or 0
    )

    original_cids = list({r["character__character_id"] for r in rows})
    characters = {
        c.character_id: c
        for c in EveCharacter.objects.filter(character_id__in=original_cids)
    }

    primary_value: dict[int, float] = {}
    primary_qty: dict[int, int] = {}
    primary_name: dict[int, str] = {}
    for r in rows:
        cid = r["character__character_id"]
        ore_tid = r["eve_type_id"]
        qty = r["total_quantity"]
        y = yield_frac.get((ore_tid, product_type_id), 0.0)
        value = qty * y * price
        char = characters.get(cid)
        primary = None
        if char:
            try:
                primary = character_primary(char)
            except (AttributeError, TypeError):
                pass
        pid = primary.character_id if primary else cid
        pname = (
            (primary.character_name or "")
            if primary
            else (r["character__character_name"] or "")
        )
        primary_value[pid] = primary_value.get(pid, 0) + value
        primary_qty[pid] = primary_qty.get(pid, 0) + qty
        primary_name.setdefault(pid, pname)

    out = [
        {
            "character_id": pid,
            "character_name": primary_name[pid],
            "total_quantity": qty,
            "total_value_isk": primary_value[pid],
        }
        for pid, qty in primary_qty.items()
    ]
    out.sort(
        key=lambda x: (x["total_value_isk"], x["total_quantity"]),
        reverse=True,
    )
    return out


def _get_ore_yield_fractions(
    material_to_products: dict[int, list[int]],
) -> dict[tuple[int, int], float]:
    """Return (ore_tid, product_tid) -> yield fraction (mineral per unit ore). Direct ore = 1.0."""
    if not material_to_products:
        return {}
    ore_ids = list(material_to_products.keys())
    vol_totals = dict(
        EveTypeMaterial.objects.filter(eve_type_id__in=ore_ids)
        .values("eve_type_id")
        .annotate(total=Sum("quantity"))
        .values_list("eve_type_id", "total")
    )
    out: dict[tuple[int, int], float] = {}
    for ore_tid, product_tids in material_to_products.items():
        total = vol_totals.get(ore_tid) or 0
        for product_tid in product_tids:
            if ore_tid == product_tid:
                out[(ore_tid, product_tid)] = 1.0
            elif total > 0:
                qty = (
                    EveTypeMaterial.objects.filter(
                        eve_type_id=ore_tid,
                        material_eve_type_id=product_tid,
                    )
                    .values_list("quantity", flat=True)
                    .first()
                    or 0
                )
                out[(ore_tid, product_tid)] = qty / total
            else:
                out[(ore_tid, product_tid)] = 0.0
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

    yield_frac = _get_ore_yield_fractions(material_to_products)
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
            y = yield_frac.get((ore_tid, product_tid), 0.0)
            price = float(prices.get(product_tid) or 0)
            value = qty * y * price
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
            else:
                existing_ids.add(cid)
                result[tid]["character_producers"].append(
                    {
                        "id": cid,
                        "name": miner_name.get(cid, ""),
                        "total_value_isk": value,
                    }
                )
