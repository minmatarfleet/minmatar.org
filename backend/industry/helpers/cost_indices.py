"""ESI industry cost indices: sync into DB and read for the planner."""

from __future__ import annotations

import logging
from typing import List, Tuple

from django.utils import timezone

from eveonline.client import _esi_to_python, esi_provider
from eveonline.helpers.db_sync import replace_with_bulk_create
from industry.helpers.facility_profiles import AMAMAKE_SYSTEM_ID
from industry.models import IndustrySystemCostIndex

logger = logging.getLogger(__name__)


def _parse_system_indices(row: dict) -> Tuple[int, float, float] | None:
    system_id = int(row.get("solar_system_id") or 0)
    if not system_id:
        return None
    manufacturing = 0.0
    reaction = 0.0
    for entry in row.get("cost_indices") or []:
        activity = entry.get("activity")
        cost = float(entry.get("cost_index") or 0.0)
        if activity == "manufacturing":
            manufacturing = cost
        elif activity == "reaction":
            reaction = cost
    return system_id, manufacturing, reaction


def fetch_industry_systems_from_esi() -> List[dict]:
    """
    Fetch GET /industry/systems/ without ETag (avoids HTTPNotModified 304).

    Returns the raw list of system rows from ESI.
    """
    try:
        rows = _esi_to_python(
            esi_provider.client.Industry.GetIndustrySystems().results(
                use_etag=False
            )
        )
    except Exception as exc:
        raise ValueError(
            f"Failed to fetch ESI industry cost indices: {exc}"
        ) from exc
    if not isinstance(rows, list):
        raise ValueError(
            f"Unexpected ESI industry systems payload type: {type(rows)!r}"
        )
    return rows


def sync_industry_system_cost_indices() -> int:
    """
    Pull ESI industry systems and replace the local cost-index cache.

    Returns the number of systems stored.
    """
    rows = fetch_industry_systems_from_esi()
    now = timezone.now()
    instances: List[IndustrySystemCostIndex] = []
    for row in rows:
        parsed = _parse_system_indices(row)
        if parsed is None:
            continue
        system_id, manufacturing, reaction = parsed
        instances.append(
            IndustrySystemCostIndex(
                solar_system_id=system_id,
                manufacturing=manufacturing,
                reaction=reaction,
                updated_at=now,
            )
        )
    count = replace_with_bulk_create(
        delete_queryset=IndustrySystemCostIndex.objects.all(),
        instances=instances,
    )
    logger.info(
        "Synced industry system cost indices for %s solar system(s)",
        count,
    )
    return count


def fetch_system_cost_indices(
    system_id: int = AMAMAKE_SYSTEM_ID,
) -> Tuple[float, float]:
    """
    Return (manufacturing_index, reaction_index) for a solar system.

    Reads the Celery-backed cache. If the system is missing (empty DB / first
    deploy), runs a one-shot ESI sync then re-reads. Steady-state planner
    traffic does not call ESI.
    """
    row = IndustrySystemCostIndex.objects.filter(
        solar_system_id=system_id
    ).first()
    if row is None:
        logger.info(
            "No cached cost indices for system %s; syncing from ESI once",
            system_id,
        )
        sync_industry_system_cost_indices()
        row = IndustrySystemCostIndex.objects.filter(
            solar_system_id=system_id
        ).first()
    if row is None:
        raise ValueError(f"No industry cost indices for system {system_id}")

    logger.info(
        "Cached cost indices for system %s: manufacturing=%.6f reaction=%.6f",
        system_id,
        row.manufacturing,
        row.reaction,
    )
    return float(row.manufacturing), float(row.reaction)
