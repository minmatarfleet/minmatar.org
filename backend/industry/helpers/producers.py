"""
Relevant character and corporation industry jobs for a product type.

Jobs are matched by blueprint/reaction type and activity (manufacturing=1, reaction=11)
that produce the given product type_id.
"""

from django.db.models import Q

from eveuniverse.models import EveIndustryActivityProduct

from eveonline.models import (
    EveCharacterIndustryJob,
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


def get_producers_for_types(product_type_ids):
    """
    Batch: for each product type_id, return character_producers and corporation_producers.
    Returns dict[type_id, {"character_producers": [...], "corporation_producers": [...]}].
    """
    if not product_type_ids:
        return {}
    type_ids = list(product_type_ids)
    # (blueprint_type_id, activity_id) -> list of product_eve_type_id
    rows = EveIndustryActivityProduct.objects.filter(
        product_eve_type_id__in=type_ids,
        activity_id__in=PRODUCTION_ACTIVITIES,
    ).values_list("eve_type_id", "activity_id", "product_eve_type_id")
    blueprint_activity_to_types = {}
    for bid, aid, tid in rows:
        key = (bid, aid)
        if key not in blueprint_activity_to_types:
            blueprint_activity_to_types[key] = []
        blueprint_activity_to_types[key].append(tid)
    if not blueprint_activity_to_types:
        return {
            tid: {"character_producers": [], "corporation_producers": []}
            for tid in type_ids
        }
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
    result = {
        tid: {"character_producers": [], "corporation_producers": []}
        for tid in type_ids
    }
    char_seen = {tid: set() for tid in type_ids}
    for bid, aid, cid, cname in char_jobs:
        key = (bid, aid)
        for tid in blueprint_activity_to_types.get(key, []):
            if cid not in char_seen[tid]:
                char_seen[tid].add(cid)
                result[tid]["character_producers"].append(
                    {"id": cid, "name": cname or ""}
                )
    corp_seen = {tid: set() for tid in type_ids}
    for bid, aid, cid, cname in corp_jobs:
        key = (bid, aid)
        for tid in blueprint_activity_to_types.get(key, []):
            if cid not in corp_seen[tid]:
                corp_seen[tid].add(cid)
                result[tid]["corporation_producers"].append(
                    {"id": cid, "name": cname or ""}
                )
    return result
