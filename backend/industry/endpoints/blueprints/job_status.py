"""Batch lookup of current industry jobs by blueprint item_id (ESI blueprint_id)."""

from __future__ import annotations

from typing import Dict, Iterable

from eveonline.models import EveCharacterIndustryJob, EveCorporationIndustryJob

# ESI industry job statuses that are not yet finished (product not delivered / job not closed).
CURRENT_JOB_STATUSES = frozenset({"active", "paused", "ready"})


def current_activity_by_item_id(item_ids: Iterable[int]) -> Dict[int, int]:
    """
    Map blueprint item_id -> one current activity_id.

    Uses two queries (character + corporation jobs). When multiple current jobs
    exist for the same item, keeps the newest by end_date / job_id.
    """
    ids = list(dict.fromkeys(item_ids))
    if not ids:
        return {}

    out: Dict[int, int] = {}
    for qs in (
        EveCharacterIndustryJob.objects.filter(
            blueprint_id__in=ids, status__in=CURRENT_JOB_STATUSES
        )
        .order_by("-end_date", "-job_id")
        .values_list("blueprint_id", "activity_id"),
        EveCorporationIndustryJob.objects.filter(
            blueprint_id__in=ids, status__in=CURRENT_JOB_STATUSES
        )
        .order_by("-end_date", "-job_id")
        .values_list("blueprint_id", "activity_id"),
    ):
        for blueprint_id, activity_id in qs:
            if blueprint_id not in out:
                out[blueprint_id] = activity_id
    return out
