"""Load invention recipes and decryptors from CCP's JSONL static data export.

eveuniverse has no invention success chance, so the planner keeps its own
copy of every blueprint's invention activity (T1 blueprint → T2 copy, ancient
relic → T3 copy) plus the generic decryptors. The download and the zip reader
are shared with the capability engine.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from django.db import transaction
from django.db.models import Max

from capabilities.engine.sde import _Source
from capabilities.services import download_build, latest_published_build
from industry.models import InventionDecryptor, InventionOutcome

logger = logging.getLogger(__name__)

CATEGORY_BLUEPRINT = 9
GROUP_GENERIC_DECRYPTOR = 1304

ATTR_PROBABILITY_MULTIPLIER = 1112
ATTR_ME_MODIFIER = 1113
ATTR_TE_MODIFIER = 1114
ATTR_RUNS_MODIFIER = 1124

ENCRYPTION_SUFFIX = "Encryption Methods"


def _en(value) -> str:
    if isinstance(value, dict):
        return str(value.get("en") or "")
    return str(value or "")


def extract(path: str | Path) -> Tuple[int, List[dict], List[dict]]:
    """Read (build, outcome rows, decryptor rows) from a CCP zip or directory."""
    source = _Source(path)
    build = 0
    for row in source.rows("_sde"):
        build = int(row.get("buildNumber") or 0)

    category_of_group: Dict[int, int] = {
        int(row["_key"]): int(row.get("categoryID") or 0)
        for row in source.rows("groups")
    }
    types: Dict[int, dict] = {}
    for row in source.rows("types"):
        types[int(row["_key"])] = {
            "name": _en(row.get("name")),
            "group_id": int(row.get("groupID") or 0),
            "published": bool(row.get("published")),
        }

    blueprints = {int(row["_key"]): row for row in source.rows("blueprints")}

    def manufactured_by(blueprint_type_id: int) -> Optional[int]:
        bp = blueprints.get(blueprint_type_id) or {}
        products = (
            bp.get("activities", {}).get("manufacturing", {}).get("products")
        )
        return int(products[0]["typeID"]) if products else None

    outcomes: List[dict] = []
    for source_id, bp in blueprints.items():
        activities = bp.get("activities", {})
        invention = activities.get("invention")
        if not invention:
            continue
        source_type = types.get(source_id, {})
        category = category_of_group.get(source_type.get("group_id", 0), 0)
        kind = (
            InventionOutcome.SOURCE_T1_BLUEPRINT
            if category == CATEGORY_BLUEPRINT
            else InventionOutcome.SOURCE_RELIC
        )
        skills = [int(s["typeID"]) for s in invention.get("skills", [])]
        encryption = next(
            (
                sid
                for sid in skills
                if types.get(sid, {})
                .get("name", "")
                .endswith(ENCRYPTION_SUFFIX)
            ),
            None,
        )
        science = [sid for sid in skills if sid != encryption]
        materials = [
            [int(m["typeID"]), int(m["quantity"])]
            for m in invention.get("materials", [])
        ]
        for product in invention.get("products", []):
            blueprint_type_id = int(product["typeID"])
            product_type_id = manufactured_by(blueprint_type_id)
            if product_type_id is None:
                continue
            if not types.get(product_type_id, {}).get("published"):
                continue
            outcomes.append(
                {
                    "source_type_id": source_id,
                    "source_name": source_type.get("name", ""),
                    "source_kind": kind,
                    "source_product_type_id": (
                        manufactured_by(source_id)
                        if kind == InventionOutcome.SOURCE_T1_BLUEPRINT
                        else None
                    ),
                    "copy_time_seconds": int(
                        activities.get("copying", {}).get("time") or 0
                    ),
                    "blueprint_type_id": blueprint_type_id,
                    "product_type_id": product_type_id,
                    "probability": float(product.get("probability") or 0.0),
                    "runs": int(product.get("quantity") or 1),
                    "time_seconds": int(invention.get("time") or 0),
                    "materials": materials,
                    "encryption_skill_id": encryption,
                    "science_skill_ids": science,
                    "sde_build": build,
                }
            )

    decryptor_ids = {
        tid
        for tid, info in types.items()
        if info["group_id"] == GROUP_GENERIC_DECRYPTOR and info["published"]
    }
    decryptors: List[dict] = []
    for row in source.rows("typeDogma"):
        tid = int(row["_key"])
        if tid not in decryptor_ids:
            continue
        attrs = {
            int(a["attributeID"]): float(a["value"])
            for a in row.get("dogmaAttributes", [])
        }
        decryptors.append(
            {
                "type_id": tid,
                "name": types[tid]["name"],
                "probability_multiplier": attrs.get(
                    ATTR_PROBABILITY_MULTIPLIER, 1.0
                ),
                "runs_modifier": int(attrs.get(ATTR_RUNS_MODIFIER, 0)),
                "me_modifier": int(attrs.get(ATTR_ME_MODIFIER, 0)),
                "te_modifier": int(attrs.get(ATTR_TE_MODIFIER, 0)),
                "sde_build": build,
            }
        )
    return build, outcomes, decryptors


def store(outcomes: List[dict], decryptors: List[dict]) -> Tuple[int, int]:
    """Replace every invention row with this build's rows."""
    with transaction.atomic():
        InventionOutcome.objects.all().delete()
        InventionOutcome.objects.bulk_create(
            [InventionOutcome(**row) for row in outcomes], batch_size=500
        )
        InventionDecryptor.objects.all().delete()
        InventionDecryptor.objects.bulk_create(
            [InventionDecryptor(**row) for row in decryptors]
        )
    return len(outcomes), len(decryptors)


def load_from_path(path: str | Path) -> Tuple[int, int, int]:
    """Load a local CCP SDE zip or unpacked directory. Returns (build, n, n)."""
    build, outcomes, decryptors = extract(path)
    if not outcomes:
        raise ValueError(f"No invention rows found in {path}")
    n_outcomes, n_decryptors = store(outcomes, decryptors)
    logger.info(
        "Loaded invention data from SDE build %s: %s outcomes, %s decryptors",
        build,
        n_outcomes,
        n_decryptors,
    )
    return build, n_outcomes, n_decryptors


def stored_build() -> int:
    return int(
        InventionOutcome.objects.aggregate(build=Max("sde_build"))["build"]
        or 0
    )


def refresh_if_new() -> Optional[int]:
    """Download CCP's newest SDE when it is newer than our rows. Returns it."""
    latest = latest_published_build()
    if stored_build() >= latest:
        return None
    with tempfile.TemporaryDirectory() as directory:
        path = download_build(latest, directory)
        load_from_path(path)
    return latest
