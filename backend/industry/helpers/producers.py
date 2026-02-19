"""
Relevant character and corporation industry jobs for a product type.

Jobs are matched by blueprint/reaction type and activity (manufacturing=1, reaction=11)
that produce the given product type_id.  Planetary interaction producers are also
included when a character's planet outputs match the requested type.
"""

from django.db.models import Q

from eveuniverse.models import EveIndustryActivityProduct

from eveonline.models import (
    EveCharacterIndustryJob,
    EveCharacterPlanetOutput,
    EveCorporationIndustryJob,
)

ACTIVITY_MANUFACTURING = 1
ACTIVITY_REACTION = 11
PRODUCTION_ACTIVITIES = (ACTIVITY_MANUFACTURING, ACTIVITY_REACTION)


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
    Characters who have industry jobs producing this product type.
    Returns list of {"id": character_id, "name": character_name}, distinct.
    """
    pairs = _blueprint_activity_pairs_for_product_type(product_type_id)
    if not pairs:
        return []
    q = Q()
    for blueprint_type_id, activity_id in pairs:
        q |= Q(blueprint_type_id=blueprint_type_id, activity_id=activity_id)
    jobs = (
        EveCharacterIndustryJob.objects.filter(q)
        .select_related("character")
        .values_list("character__character_id", "character__character_name")
        .distinct()
    )
    seen = set()
    out = []
    for cid, cname in jobs:
        if cid not in seen:
            seen.add(cid)
            out.append({"id": cid, "name": cname or ""})
    return out


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
    """Populate planetary_producers from EveCharacterPlanetOutput."""
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


def get_producers_for_types(product_type_ids):
    """
    Batch: for each product type_id, return character_producers,
    corporation_producers, and planetary_producers.
    """
    if not product_type_ids:
        return {}
    type_ids = list(product_type_ids)
    result = {
        tid: {
            "character_producers": [],
            "corporation_producers": [],
            "planetary_producers": [],
        }
        for tid in type_ids
    }
    blueprint_activity_to_types = _build_blueprint_activity_to_types(type_ids)
    if blueprint_activity_to_types:
        _fill_job_producers(result, type_ids, blueprint_activity_to_types)
    _fill_planetary_producers(result, type_ids)
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
