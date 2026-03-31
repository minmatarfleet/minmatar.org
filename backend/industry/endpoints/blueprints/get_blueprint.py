"""GET /{item_id} - one blueprint by ESI item_id with current and historical industry jobs."""

from __future__ import annotations

from typing import List, Tuple

from django.db.models import QuerySet
from eveuniverse.models import EveType

from app.errors import ErrorResponse
from eveonline.models import (
    EveCharacter,
    EveCharacterBlueprint,
    EveCharacterIndustryJob,
    EveCorporationBlueprint,
    EveCorporationIndustryJob,
    EvePlayer,
)
from industry.endpoints.blueprints.schemas import (
    BlueprintDetailResponse,
    BlueprintIndustryJobResponse,
    BlueprintOwnerResponse,
)

# ESI industry job statuses that are not yet finished (product not delivered / job not closed).
_CURRENT_JOB_STATUSES = frozenset({"active", "paused", "ready"})

PATH = "{int:item_id}"
METHOD = "get"
ROUTE_SPEC = {
    "summary": (
        "Get a single blueprint by ESI item_id with current and historical "
        "industry jobs (from synced character and corporation job data)."
    ),
    "response": {
        200: BlueprintDetailResponse,
        404: ErrorResponse,
    },
}


def _primary_eve_character_id(user_id: int | None) -> int | None:
    if user_id is None:
        return None
    primary_pk = (
        EvePlayer.objects.filter(user_id=user_id)
        .values_list("primary_character_id", flat=True)
        .first()
    )
    if not primary_pk:
        return None
    return (
        EveCharacter.objects.filter(pk=primary_pk)
        .values_list("character_id", flat=True)
        .first()
    )


def _char_job_to_response(
    job: EveCharacterIndustryJob,
) -> BlueprintIndustryJobResponse:
    ch = job.character
    return BlueprintIndustryJobResponse(
        job_id=job.job_id,
        source="character",
        activity_id=job.activity_id,
        blueprint_type_id=job.blueprint_type_id,
        status=job.status,
        installer_id=job.installer_id,
        start_date=job.start_date,
        end_date=job.end_date,
        completed_date=job.completed_date,
        duration=job.duration,
        runs=job.runs,
        licensed_runs=job.licensed_runs,
        cost=job.cost,
        location_id=job.location_id,
        output_location_id=job.output_location_id,
        blueprint_location_id=job.blueprint_location_id,
        facility_id=job.facility_id,
        character_id=ch.character_id,
        character_name=ch.character_name,
        corporation_id=None,
        corporation_name=None,
    )


def _corp_job_to_response(
    job: EveCorporationIndustryJob,
) -> BlueprintIndustryJobResponse:
    corp = job.corporation
    return BlueprintIndustryJobResponse(
        job_id=job.job_id,
        source="corporation",
        activity_id=job.activity_id,
        blueprint_type_id=job.blueprint_type_id,
        status=job.status,
        installer_id=job.installer_id,
        start_date=job.start_date,
        end_date=job.end_date,
        completed_date=job.completed_date,
        duration=job.duration,
        runs=job.runs,
        licensed_runs=job.licensed_runs,
        cost=job.cost,
        location_id=job.location_id,
        output_location_id=job.output_location_id,
        blueprint_location_id=job.blueprint_location_id,
        facility_id=job.facility_id,
        character_id=None,
        character_name=None,
        corporation_id=corp.corporation_id,
        corporation_name=corp.name or None,
    )


def _collect_jobs(item_id: int) -> List[BlueprintIndustryJobResponse]:
    char_qs: QuerySet[EveCharacterIndustryJob] = (
        EveCharacterIndustryJob.objects.filter(blueprint_id=item_id)
        .select_related("character")
        .order_by("-end_date", "-job_id")
    )
    corp_qs: QuerySet[EveCorporationIndustryJob] = (
        EveCorporationIndustryJob.objects.filter(blueprint_id=item_id)
        .select_related("corporation")
        .order_by("-end_date", "-job_id")
    )
    rows: List[BlueprintIndustryJobResponse] = [
        _char_job_to_response(j) for j in char_qs
    ]
    rows.extend(_corp_job_to_response(j) for j in corp_qs)
    rows.sort(key=lambda r: (r.end_date, r.job_id), reverse=True)
    return rows


def _split_current_historical(
    jobs: List[BlueprintIndustryJobResponse],
) -> Tuple[
    List[BlueprintIndustryJobResponse], List[BlueprintIndustryJobResponse]
]:
    current: List[BlueprintIndustryJobResponse] = []
    historical: List[BlueprintIndustryJobResponse] = []
    for j in jobs:
        if j.status in _CURRENT_JOB_STATUSES:
            current.append(j)
        else:
            historical.append(j)
    return current, historical


def get_blueprint(request, item_id: int):
    char_bp = (
        EveCharacterBlueprint.objects.filter(item_id=item_id)
        .select_related("character")
        .first()
    )
    corp_bp = None
    if char_bp is None:
        corp_bp = (
            EveCorporationBlueprint.objects.filter(item_id=item_id)
            .select_related("corporation", "corporation__ceo")
            .first()
        )
    if char_bp is None and corp_bp is None:
        return 404, ErrorResponse(
            detail=f"Blueprint item_id {item_id} not found."
        )

    if char_bp is not None:
        ch = char_bp.character
        type_name = (
            EveType.objects.filter(pk=char_bp.type_id)
            .values_list("name", flat=True)
            .first()
            or ""
        )
        owner = BlueprintOwnerResponse(
            entity_id=ch.character_id,
            entity_type="character",
            primary_character_id=_primary_eve_character_id(ch.user_id),
        )
        bp = char_bp
    else:
        corp = corp_bp.corporation
        ceo = corp.ceo
        type_name = (
            EveType.objects.filter(pk=corp_bp.type_id)
            .values_list("name", flat=True)
            .first()
            or ""
        )
        owner = BlueprintOwnerResponse(
            entity_id=corp.corporation_id,
            entity_type="corporation",
            primary_character_id=_primary_eve_character_id(
                ceo.user_id if ceo else None
            ),
        )
        bp = corp_bp

    jobs = _collect_jobs(item_id)
    current_jobs, historical_jobs = _split_current_historical(jobs)

    return 200, BlueprintDetailResponse(
        item_id=bp.item_id,
        type_id=bp.type_id,
        blueprint_name=type_name,
        type_name=type_name,
        location_id=bp.location_id,
        location_flag=bp.location_flag,
        material_efficiency=bp.material_efficiency,
        time_efficiency=bp.time_efficiency,
        quantity=bp.quantity,
        runs=bp.runs,
        is_original=bp.quantity == -1,
        owner=owner,
        current_jobs=current_jobs,
        historical_jobs=historical_jobs,
    )
