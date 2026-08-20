"""Leadership endpoints: create/manage campaigns, results, changelog."""

import logging
from collections import defaultdict

from django.utils import timezone
from ninja import Router

from authentication import AuthBearer
from surveys.constants import (
    SEGMENT_ALL,
    STATUS_CLOSED,
    STATUS_OPEN,
    TYPE_TEXT,
)
from surveys.definitions import default_definition, get_definition
from surveys.endpoints.schemas import (
    AggregateSchema,
    ChangelogEntryInput,
    CreateCampaignRequest,
    CampaignSchema,
    ResultsSchema,
    UpdateCampaignRequest,
)
from surveys.endpoints.serializers import serialize_campaign
from surveys.helpers.aggregation import compute_aggregates
from surveys.helpers.permissions import require_manage, require_superuser
from surveys.helpers.teams import resolve_dynamic_rows
from surveys.models import (
    SurveyAnswer,
    SurveyCampaign,
    SurveyChangelogEntry,
)

logger = logging.getLogger(__name__)

router = Router(tags=["Surveys - Manage"])


@router.get("/", response={200: list, 403: dict}, auth=AuthBearer())
def list_campaigns(request):
    denied = require_manage(request)
    if denied:
        return denied
    return 200, [
        serialize_campaign(c).dict() for c in SurveyCampaign.objects.all()
    ]


@router.post(
    "/",
    response={200: CampaignSchema, 400: dict, 403: dict},
    auth=AuthBearer(),
)
def create_campaign(request, payload: CreateCampaignRequest):
    denied = require_manage(request)
    if denied:
        return denied
    definition = (
        get_definition(payload.definition_key)
        if payload.definition_key
        else default_definition()
    )
    if SurveyCampaign.objects.filter(
        year=payload.year, quarter=payload.quarter
    ).exists():
        return 400, {"detail": "A campaign already exists for that quarter."}
    campaign = SurveyCampaign.objects.create(
        year=payload.year,
        quarter=payload.quarter,
        definition_key=definition.key,
        title=payload.title
        or f"{payload.year} Q{payload.quarter} Community Survey",
        status=STATUS_OPEN if payload.open_now else "draft",
        opens_at=timezone.now() if payload.open_now else None,
        created_by=request.user,
    )
    return 200, serialize_campaign(campaign)


@router.patch(
    "/{campaign_id}",
    response={200: CampaignSchema, 400: dict, 403: dict, 404: dict},
    auth=AuthBearer(),
)
def update_campaign(request, campaign_id: int, payload: UpdateCampaignRequest):
    denied = require_manage(request)
    if denied:
        return denied
    campaign = SurveyCampaign.objects.filter(pk=campaign_id).first()
    if not campaign:
        return 404, {"detail": "Campaign not found."}
    if payload.status:
        campaign.status = payload.status
        if payload.status == STATUS_OPEN and not campaign.opens_at:
            campaign.opens_at = timezone.now()
        if payload.status == STATUS_CLOSED and not campaign.closes_at:
            campaign.closes_at = timezone.now()
    if payload.opens_at is not None:
        campaign.opens_at = payload.opens_at or None
    if payload.closes_at is not None:
        campaign.closes_at = payload.closes_at or None
    campaign.save()

    if campaign.status == STATUS_CLOSED:
        try:
            compute_aggregates(campaign)
        except Exception:  # pragma: no cover - defensive
            logger.exception("aggregate recompute failed for %s", campaign.pk)
    return 200, serialize_campaign(campaign)


@router.get(
    "/{campaign_id}/results",
    response={200: ResultsSchema, 403: dict, 404: dict},
    auth=AuthBearer(),
)
def get_results(request, campaign_id: int, segment: str = SEGMENT_ALL):
    denied = require_superuser(request)
    if denied:
        return denied
    campaign = SurveyCampaign.objects.filter(pk=campaign_id).first()
    if not campaign:
        return 404, {"detail": "Campaign not found."}
    if not campaign.aggregates.exists():
        try:
            compute_aggregates(campaign)
        except Exception:  # pragma: no cover - defensive
            logger.exception("live aggregate compute failed")
    rows = campaign.aggregates.filter(segment_key=segment)
    return 200, ResultsSchema(
        campaign_id=campaign.pk,
        segment_key=segment,
        aggregates=[
            AggregateSchema(
                question_key=r.question_key,
                segment_key=r.segment_key,
                n=r.n,
                mean=r.mean,
                distribution=r.distribution,
            )
            for r in rows
        ],
    )


@router.post(
    "/{campaign_id}/changelog",
    response={200: dict, 403: dict, 404: dict},
    auth=AuthBearer(),
)
def post_changelog(request, campaign_id: int, payload: ChangelogEntryInput):
    denied = require_manage(request)
    if denied:
        return denied
    campaign = SurveyCampaign.objects.filter(pk=campaign_id).first()
    if not campaign:
        return 404, {"detail": "Campaign not found."}
    entry = SurveyChangelogEntry.objects.create(
        campaign=campaign,
        heading=payload.heading,
        body_markdown=payload.body_markdown,
        sort_order=payload.sort_order,
        published=payload.published,
    )
    return 200, {"ok": True, "id": entry.pk}


def _row_label_map(q) -> dict:
    rows = (
        resolve_dynamic_rows(q.row_source)
        if q.row_source
        else [{"key": r[0], "label": r[1]} for r in q.rows]
    )
    return {r["key"]: r["label"] for r in rows}


def _question_row(q, aggs) -> dict:
    a = aggs.get(q.key)
    return {
        "key": q.key,
        "label": q.label,
        "type": q.type,
        "group": q.group,
        "scale_labels": (list(q.scale_labels) if q.scale_labels else None),
        "n": a.n if a else 0,
        "mean": a.mean if a else None,
        "distribution": a.distribution if a else {},
        "rows": _row_label_map(q) if q.type == "matrix" else {},
    }


def _build_sections(definition, aggs) -> tuple[list, list]:
    """Return (sections, write_in_keys): non-text questions grouped by block,
    and the (key, label, block-title) tuples for the free-text write-ins."""
    sections = []
    write_in_keys = []
    for block in definition.blocks:
        questions = []
        for q in block.questions:
            if q.type == TYPE_TEXT:
                write_in_keys.append((q.key, q.label, block.title))
                continue
            questions.append(_question_row(q, aggs))
        if questions:
            sections.append(
                {
                    "key": block.key,
                    "title": block.title,
                    "questions": questions,
                }
            )
    return sections, write_in_keys


def _write_in_row(answer) -> dict:
    """One free-text answer attributed to its author (portrait + name)."""
    snap = answer.response.context_snapshot or {}
    cname = snap.get("character_name") or (
        answer.response.user.username if answer.response.user_id else ""
    )
    return {
        "text": answer.text_value,
        "character_id": snap.get("character_id"),
        "character_name": cname,
        "corporation_id": answer.response.corporation_id
        or snap.get("corporation_id"),
        "corporation_name": answer.response.corporation_name
        or snap.get("corporation_name", ""),
    }


def _collect_write_ins(campaign, write_in_keys) -> list:
    """Free-text responses grouped by question, attributed to authors."""
    out = []
    for key, label, section in write_in_keys:
        rows = (
            SurveyAnswer.objects.filter(
                response__campaign=campaign, question_key=key
            )
            .exclude(text_value="")
            .select_related("response__user")[:500]
        )
        out.append(
            {
                "key": key,
                "label": label,
                "section": section,
                "responses": [_write_in_row(a) for a in rows],
            }
        )
    return out


@router.get(
    "/{campaign_id}/report",
    response={200: dict, 403: dict, 404: dict},
    auth=AuthBearer(),
    summary="Full single-survey results, grouped by section, plus write-ins.",
)
def get_report(request, campaign_id: int):
    denied = require_superuser(request)
    if denied:
        return denied
    campaign = SurveyCampaign.objects.filter(pk=campaign_id).first()
    if not campaign:
        return 404, {"detail": "Campaign not found."}

    from surveys.definitions.effective import build_effective_definition

    definition = build_effective_definition(campaign)
    if not definition:
        return 404, {"detail": "Survey definition not found."}

    if not campaign.aggregates.exists() and campaign.responses.exists():
        try:
            compute_aggregates(campaign)
        except Exception:  # pragma: no cover - defensive
            logger.exception("report aggregate compute failed")

    aggs = {
        a.question_key: a
        for a in campaign.aggregates.filter(segment_key="all")
    }

    sections, write_in_keys = _build_sections(definition, aggs)
    write_ins = _collect_write_ins(campaign, write_in_keys)

    return 200, {
        "campaign_id": campaign.pk,
        "title": campaign.title,
        "response_count": campaign.responses.count(),
        "sections": sections,
        "write_ins": write_ins,
    }


@router.get(
    "/{campaign_id}/corp-progress",
    response={200: dict, 403: dict, 404: dict},
    auth=AuthBearer(),
    summary="Per-corporation fill-out progress (submitted / distinct players).",
)
def get_corp_progress(request, campaign_id: int):
    denied = require_manage(request)
    if denied:
        return denied
    campaign = SurveyCampaign.objects.filter(pk=campaign_id).first()
    if not campaign:
        return 404, {"detail": "Campaign not found."}

    from eveonline.models import EveCorporation, EvePlayer
    from surveys.helpers.corp_history import FL33T_ALLIANCE_ID

    # Submitted count per corp (from snapshotted corporation on each response).
    submitted: dict[int, int] = defaultdict(int)
    submitted_by_name: dict[str, int] = defaultdict(int)
    for r in campaign.responses.all().only(
        "corporation_id", "corporation_name"
    ):
        if r.corporation_id:
            submitted[r.corporation_id] += 1
        elif r.corporation_name:
            submitted_by_name[r.corporation_name] += 1

    corps = []
    for corp in EveCorporation.objects.filter(
        alliance__alliance_id=FL33T_ALLIANCE_ID
    ).order_by("name"):
        total = (
            EvePlayer.objects.filter(
                primary_character__corporation_id=corp.corporation_id
            )
            .exclude(user__community_status__status="on_leave")
            .count()
        )
        done = submitted.get(corp.corporation_id, 0) or submitted_by_name.get(
            corp.name, 0
        )
        if total == 0 and done == 0:
            continue
        corps.append(
            {
                "corporation_id": corp.corporation_id,
                "corporation_name": corp.name,
                "submitted": done,
                "total": total,
            }
        )
    corps.sort(key=lambda c: c["submitted"], reverse=True)
    return 200, {"campaign_id": campaign.pk, "corps": corps}


@router.get(
    "/{campaign_id}/corp-report",
    response={200: dict, 403: dict, 404: dict},
    auth=AuthBearer(),
    summary="Per-corp aggregates for the corporation-experience section.",
)
def get_corp_report(request, campaign_id: int):
    denied = require_superuser(request)
    if denied:
        return denied
    scope, own_corp = "all", None
    campaign = SurveyCampaign.objects.filter(pk=campaign_id).first()
    if not campaign:
        return 404, {"detail": "Campaign not found."}
    definition = get_definition(campaign.definition_key)
    if not definition:
        return 404, {"detail": "Survey definition not found."}

    if not campaign.aggregates.exists() and campaign.responses.exists():
        try:
            compute_aggregates(campaign)
        except Exception:  # pragma: no cover - defensive
            logger.exception("corp report aggregate compute failed")

    corp_questions = [
        (q.key, q.label)
        for q in definition.all_questions()
        if q.key.startswith("corp.")
    ]
    corp_keys = {k for k, _ in corp_questions}

    MIN_N = 3  # suppress tiny corps to protect anonymity
    rows = campaign.aggregates.filter(
        question_key__in=corp_keys, segment_key__startswith="corp:"
    )
    by_corp: dict = defaultdict(dict)
    for a in rows:
        corp_name = a.segment_key.split("corp:", 1)[1]
        by_corp[corp_name][a.question_key] = a

    if scope == "own":
        by_corp = {own_corp: by_corp.get(own_corp, {})}

    corps_out = []
    for corp_name, aggs in sorted(by_corp.items()):
        # n for the corp = max respondents on any corp question.
        n = max((a.n for a in aggs.values()), default=0)
        suppressed = n < MIN_N
        questions = []
        for key, label in corp_questions:
            a = aggs.get(key)
            questions.append(
                {
                    "question_key": key,
                    "label": label,
                    "mean": None if suppressed else (a.mean if a else None),
                    "n": (a.n if a else 0),
                }
            )
        corps_out.append(
            {
                "corp": corp_name,
                "n": n,
                "suppressed": suppressed,
                "questions": questions,
            }
        )

    return 200, {
        "campaign_id": campaign.pk,
        "scope": scope,
        "min_n": MIN_N,
        "corps": corps_out,
    }
