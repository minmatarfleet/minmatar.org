"""
Characters and corporations dealing with a product type.

character_producers: primary character per user (industry jobs, planetary output, and/or mining).
corporation_producers: corporations with industry jobs.
planetary_producers: per-planet PI details (character, planet, output_type).
mining_producers: characters who mine ores relevant to the product (last 30 days).
"""

from datetime import timedelta

from django.db.models import Q, Sum
from django.utils import timezone

from eveuniverse.models import EveIndustryActivityProduct, EveTypeMaterial

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


def _resolve_to_primary_producers(character_refs):
    """
    Map each producing character to their user's primary character; dedupe by primary.
    Returns list of {"id": character_id, "name": character_name}. Characters without
    a linked user/primary are left as-is.
    """
    if not character_refs:
        return []
    ids = [c["id"] for c in character_refs]
    characters = {
        c.character_id: c
        for c in EveCharacter.objects.filter(character_id__in=ids)
    }
    seen = set()
    out = []
    for ref in character_refs:
        cid = ref["id"]
        cname = ref["name"] or ""
        char = characters.get(cid)
        primary = None
        if char:
            try:
                primary = character_primary(char)
            except (AttributeError, TypeError):
                pass
        if primary:
            pid, pname = primary.character_id, primary.character_name or ""
            if pid not in seen:
                seen.add(pid)
                out.append({"id": pid, "name": pname})
        else:
            if cid not in seen:
                seen.add(cid)
                out.append({"id": cid, "name": cname})
    return out


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


def _fill_job_producers(result, type_ids, blueprint_activity_to_types):
    """Populate character_producers and corporation_producers from industry jobs."""
    q = Q()
    for (bid, aid), _ in blueprint_activity_to_types.items():
        q |= Q(blueprint_type_id=bid, activity_id=aid)
    char_jobs = (
        EveCharacterIndustryJob.objects.filter(q)
        .select_related("character")
        .values_list(
            "blueprint_type_id",
            "activity_id",
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
            "corporation__corporation_id",
            "corporation__name",
        )
    )
    char_seen = {tid: set() for tid in type_ids}
    for bid, aid, cid, cname in char_jobs:
        for tid in blueprint_activity_to_types.get((bid, aid), []):
            if cid not in char_seen[tid]:
                char_seen[tid].add(cid)
                result[tid]["character_producers"].append(
                    {"id": cid, "name": cname or ""}
                )
    corp_seen = {tid: set() for tid in type_ids}
    for bid, aid, cid, cname in corp_jobs:
        for tid in blueprint_activity_to_types.get((bid, aid), []):
            if cid not in corp_seen[tid]:
                corp_seen[tid].add(cid)
                result[tid]["corporation_producers"].append(
                    {"id": cid, "name": cname or ""}
                )


def _fill_planetary_producers(result, type_ids):
    """Populate planetary_producers from EveCharacterPlanetOutput and add those characters to character_producers."""
    planet_outputs = (
        EveCharacterPlanetOutput.objects.filter(eve_type_id__in=type_ids)
        .select_related("planet__character")
        .values_list(
            "eve_type_id",
            "output_type",
            "planet__character__character_id",
            "planet__character__character_name",
            "planet__planet_id",
            "planet__solar_system_id",
            "planet__planet_type",
        )
    )
    # Characters already in character_producers (from industry jobs)
    char_seen = {
        tid: {c["id"] for c in result[tid]["character_producers"]}
        for tid in type_ids
    }
    planet_seen = {tid: set() for tid in type_ids}
    for (
        eve_type_id,
        output_type,
        cid,
        cname,
        planet_id,
        system_id,
        ptype,
    ) in planet_outputs:
        key = (cid, planet_id)
        if key not in planet_seen[eve_type_id]:
            planet_seen[eve_type_id].add(key)
            result[eve_type_id]["planetary_producers"].append(
                {
                    "character_id": cid,
                    "character_name": cname or "",
                    "planet_id": planet_id,
                    "solar_system_id": system_id,
                    "planet_type": ptype or "",
                    "output_type": output_type,
                }
            )
        if cid not in char_seen[eve_type_id]:
            char_seen[eve_type_id].add(cid)
            result[eve_type_id]["character_producers"].append(
                {"id": cid, "name": cname or ""}
            )


def get_producers_for_types(product_type_ids):
    """
    Batch: for each product type_id, return character_producers,
    corporation_producers, planetary_producers, and mining_producers.
    """
    if not product_type_ids:
        return {}
    type_ids = list(product_type_ids)
    result = {
        tid: {
            "character_producers": [],
            "corporation_producers": [],
            "planetary_producers": [],
            "mining_producers": [],
        }
        for tid in type_ids
    }
    blueprint_activity_to_types = _build_blueprint_activity_to_types(type_ids)
    if blueprint_activity_to_types:
        _fill_job_producers(result, type_ids, blueprint_activity_to_types)
    _fill_planetary_producers(result, type_ids)
    _fill_mining_producers(result, type_ids)
    for tid in type_ids:
        result[tid]["character_producers"] = _resolve_to_primary_producers(
            result[tid]["character_producers"]
        )
    return result


def get_planetary_producers_for_type(product_type_id: int):
    """
    Characters whose planetary colonies produce or harvest this type.
    Returns list of dicts with character_id, character_name, planet_id,
    solar_system_id, planet_type, output_type.
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
    return out


# ---------------------------------------------------------------------------
# Mining producers
# ---------------------------------------------------------------------------

MINING_WINDOW_DAYS = 30


def _ore_type_ids_for_material(material_type_id: int) -> set[int]:
    """Return type_ids of ores/items whose reprocessing yields this material."""
    return set(
        EveTypeMaterial.objects.filter(
            material_eve_type_id=material_type_id,
        ).values_list("eve_type_id", flat=True)
    )


def get_mining_producers_for_type(product_type_id: int):
    """
    Characters who mined ores relevant to this product type in the last 30 days.

    Two lookup paths:
      1. Direct: the product type IS an ore that was mined.
      2. Reprocessing: the product type is a mineral; find ores whose
         EveTypeMaterial rows list it as an output, then find miners of
         those ores.

    Returns list of dicts sorted by total_quantity descending:
        {"character_id", "character_name", "total_quantity"}
    Characters are resolved to their user's primary character.
    """
    ore_type_ids = _ore_type_ids_for_material(product_type_id)
    ore_type_ids.add(product_type_id)

    cutoff = timezone.now().date() - timedelta(days=MINING_WINDOW_DAYS)

    rows = (
        EveCharacterMiningEntry.objects.filter(
            eve_type_id__in=ore_type_ids,
            date__gte=cutoff,
        )
        .values(
            "character__character_id",
            "character__character_name",
        )
        .annotate(total_quantity=Sum("quantity"))
        .order_by("-total_quantity")
    )

    original_cids = [r["character__character_id"] for r in rows]
    characters = {
        c.character_id: c
        for c in EveCharacter.objects.filter(character_id__in=original_cids)
    }

    primary_qty: dict[int, int] = {}
    primary_name: dict[int, str] = {}
    for r in rows:
        cid = r["character__character_id"]
        qty = r["total_quantity"]
        char = characters.get(cid)
        primary = None
        if char:
            try:
                primary = character_primary(char)
            except (AttributeError, TypeError):
                pass
        if primary:
            pid, pname = primary.character_id, primary.character_name or ""
        else:
            pid = cid
            pname = r["character__character_name"] or ""
        primary_qty[pid] = primary_qty.get(pid, 0) + qty
        primary_name.setdefault(pid, pname)

    out = [
        {
            "character_id": pid,
            "character_name": primary_name[pid],
            "total_quantity": qty,
        }
        for pid, qty in primary_qty.items()
    ]
    out.sort(key=lambda x: x["total_quantity"], reverse=True)
    return out


def _fill_mining_producers(result, type_ids):
    """Populate mining_producers and add mining characters to character_producers."""
    all_ore_type_ids: set[int] = set(type_ids)
    material_to_products: dict[int, list[int]] = {}

    ore_source_rows = EveTypeMaterial.objects.filter(
        material_eve_type_id__in=type_ids,
    ).values_list("eve_type_id", "material_eve_type_id")
    for ore_tid, mat_tid in ore_source_rows:
        all_ore_type_ids.add(ore_tid)
        material_to_products.setdefault(ore_tid, []).append(mat_tid)

    for tid in type_ids:
        material_to_products.setdefault(tid, []).append(tid)

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

    char_seen = {
        tid: {c["id"] for c in result[tid]["character_producers"]}
        for tid in type_ids
    }
    # {product_type_id: {character_id: total_quantity}}
    miner_qty: dict[int, dict[int, int]] = {tid: {} for tid in type_ids}
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
            miner_qty[product_tid][cid] = (
                miner_qty[product_tid].get(cid, 0) + qty
            )
            if cid not in char_seen[product_tid]:
                char_seen[product_tid].add(cid)
                result[product_tid]["character_producers"].append(
                    {"id": cid, "name": cname}
                )

    for tid in type_ids:
        miners = [
            {
                "character_id": cid,
                "character_name": miner_name.get(cid, ""),
                "total_quantity": qty,
            }
            for cid, qty in miner_qty[tid].items()
        ]
        miners.sort(key=lambda x: x["total_quantity"], reverse=True)
        result[tid]["mining_producers"] = miners
