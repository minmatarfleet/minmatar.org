"""Load missing blueprint recipes from CCP's JSONL static data export.

eveuniverse fetches blueprint activities lazily from a third-party SDE
mirror, which can lag CCP by months: new hulls such as the Tornado Fleet
Issue then have no blueprint, so the planner cannot build them. This fills
eveuniverse's industry tables straight from CCP's blueprints.jsonl, for the
hulls and the types the industry app uses that have none yet.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Iterable, List, Set

from django.db import transaction
from eveuniverse.models import (
    EveIndustryActivity,
    EveIndustryActivityDuration,
    EveIndustryActivityMaterial,
    EveIndustryActivityProduct,
    EveIndustryActivitySkill,
    EveType,
)

from capabilities.engine.sde import _Source
from eveonline.helpers.universe import ensure_eve_types
from industry.models import IndustryOrderItem, IndustryProduct

logger = logging.getLogger(__name__)

# CCP's activity keys in blueprints.jsonl -> eveuniverse activity ids.
ACTIVITY_IDS: Dict[str, int] = {
    "manufacturing": 1,
    "research_time": 3,
    "research_material": 4,
    "copying": 5,
    "invention": 8,
    "reaction": 11,
}
BUILD_ACTIVITIES = ("manufacturing", "reaction")
CATEGORY_SHIP = 6


def wanted_product_type_ids() -> Set[int]:
    """Every published hull, plus the types the industry app builds or orders."""
    ids = (
        set(IndustryProduct.objects.values_list("eve_type_id", flat=True))
        | set(IndustryOrderItem.objects.values_list("eve_type_id", flat=True))
        | set(
            EveType.objects.filter(
                eve_group__eve_category_id=CATEGORY_SHIP, published=True
            ).values_list("id", flat=True)
        )
    )
    return {int(i) for i in ids if i}


def _built_products(row: dict) -> List[int]:
    activities = row.get("activities") or {}
    return [
        int(p["typeID"])
        for key in BUILD_ACTIVITIES
        for p in (activities.get(key) or {}).get("products") or []
    ]


def missing_blueprints(
    rows: Iterable[dict], wanted: Set[int]
) -> Dict[int, dict]:
    """{blueprint id: row} for wanted products that have no stored recipe."""
    have = set(
        EveIndustryActivityProduct.objects.filter(
            product_eve_type_id__in=wanted,
            activity_id__in=[ACTIVITY_IDS[k] for k in BUILD_ACTIVITIES],
        ).values_list("product_eve_type_id", flat=True)
    )
    need = wanted - have
    if not need:
        return {}
    return {
        int(row["_key"]): row
        for row in rows
        if need.intersection(_built_products(row))
    }


# (model, CCP list key, eveuniverse type field, CCP value key, model field)
_TYPE_ROWS = (
    (
        EveIndustryActivityMaterial,
        "materials",
        "material_eve_type_id",
        "quantity",
        "quantity",
    ),
    (
        EveIndustryActivityProduct,
        "products",
        "product_eve_type_id",
        "quantity",
        "quantity",
    ),
    (
        EveIndustryActivitySkill,
        "skills",
        "skill_eve_type_id",
        "level",
        "level",
    ),
)


def _referenced_type_ids(blueprints: Dict[int, dict]) -> Set[int]:
    type_ids: Set[int] = set(blueprints)
    for row in blueprints.values():
        for activity in (row.get("activities") or {}).values():
            for _, key, _, _, _ in _TYPE_ROWS:
                type_ids.update(
                    int(x["typeID"]) for x in activity.get(key) or []
                )
    return type_ids


def _activity_rows(
    blueprint_id: int, activity_id: int, activity: dict, known: Set[int]
) -> List[tuple]:
    """(model, instance) rows for one blueprint activity."""
    common = {"eve_type_id": blueprint_id, "activity_id": activity_id}
    rows: List[tuple] = []
    if activity.get("time") is not None:
        rows.append(
            (
                EveIndustryActivityDuration,
                EveIndustryActivityDuration(
                    time=int(activity["time"]), **common
                ),
            )
        )
    for model, key, type_field, value_key, field in _TYPE_ROWS:
        for item in activity.get(key) or []:
            type_id = int(item["typeID"])
            if type_id not in known:
                continue
            value = int(item.get(value_key) or 1)
            rows.append(
                (model, model(**{type_field: type_id, field: value}, **common))
            )
    return rows


def store_blueprints(blueprints: Dict[int, dict]) -> int:
    """Write every activity of these blueprints. Returns how many were stored."""
    if not blueprints:
        return 0
    known = set(ensure_eve_types(_referenced_type_ids(blueprints)))
    for name, activity_id in ACTIVITY_IDS.items():
        EveIndustryActivity.objects.get_or_create(
            id=activity_id,
            defaults={"name": name, "description": name.replace("_", " ")},
        )
    by_model: Dict[type, list] = {}
    stored = 0
    for blueprint_id, row in blueprints.items():
        if blueprint_id not in known:
            logger.warning("Blueprint type %s is not in EveType", blueprint_id)
            continue
        stored += 1
        for name, activity in (row.get("activities") or {}).items():
            if name not in ACTIVITY_IDS:
                continue
            for model, obj in _activity_rows(
                blueprint_id, ACTIVITY_IDS[name], activity, known
            ):
                by_model.setdefault(model, []).append(obj)
    with transaction.atomic():
        for model, objs in by_model.items():
            model.objects.bulk_create(objs, ignore_conflicts=True)
    return stored


def load_missing_blueprints(path: str | Path) -> int:
    """Fill missing recipes for wanted types from a CCP zip or directory."""
    wanted = wanted_product_type_ids()
    if not wanted:
        return 0
    blueprints = missing_blueprints(_Source(path).rows("blueprints"), wanted)
    stored = store_blueprints(blueprints)
    if stored:
        logger.info("Loaded %s blueprint(s) from CCP's SDE", stored)
    return stored
