"""Member-facing survey endpoints: discover, autofill, fill, submit, give-back."""

import logging

from django.db import transaction
from ninja import Router

from authentication import AuthBearer
from surveys.constants import STATUS_OPEN
from surveys.definitions.effective import build_effective_definition
from surveys.endpoints.schemas import (
    ActiveSurveySchema,
    ChangelogEntrySchema,
    GivebackSchema,
    MemberContextSchema,
    MyResponseSchema,
    SubmitResponseRequest,
    SubmitResult,
    SurveyQuestionsSchema,
)
from surveys.endpoints.serializers import serialize_block, serialize_campaign
from surveys.helpers.autofill import (
    build_member_context,
    build_segmentation,
    community_status,
)
from surveys.helpers.content import resolve_context
from surveys.helpers.giveback import build_giveback_card
from surveys.helpers.teams import resolve_dynamic_rows
from surveys.helpers.usage import visible_service_keys
from surveys.models import SurveyAnswer, SurveyCampaign, SurveyResponse

logger = logging.getLogger(__name__)

router = Router(tags=["Surveys"])


def _active_campaign() -> SurveyCampaign | None:
    return (
        SurveyCampaign.objects.filter(status=STATUS_OPEN)
        .order_by("-year", "-quarter")
        .first()
    )


@router.get("/active", response={200: ActiveSurveySchema}, auth=AuthBearer())
def get_active(request):
    campaign = _active_campaign()
    if not campaign:
        return 200, ActiveSurveySchema(campaign=None)
    return 200, ActiveSurveySchema(
        campaign=serialize_campaign(campaign),
        has_responded=SurveyResponse.objects.filter(
            campaign=campaign, user=request.user
        ).exists(),
    )


def _answer_value(answer):
    """Reverse the typed storage columns back into the value shape the form
    submitted (number, string, list, or matrix dict)."""
    if answer.numeric_value is not None:
        n = answer.numeric_value
        return int(n) if float(n).is_integer() else n
    if answer.json_value is not None:
        return answer.json_value
    if answer.choice_value:
        return answer.choice_value
    return answer.text_value


@router.get(
    "/{campaign_id}/response",
    response={200: MyResponseSchema, 404: dict},
    auth=AuthBearer(),
    summary="The member's own saved answers, for review/edit.",
)
def get_my_response(request, campaign_id: int):
    campaign = SurveyCampaign.objects.filter(pk=campaign_id).first()
    if not campaign:
        return 404, {"detail": "Campaign not found."}
    response = SurveyResponse.objects.filter(
        campaign=campaign, user=request.user
    ).first()
    if not response:
        return 200, MyResponseSchema(answers={}, has_responded=False)
    return 200, MyResponseSchema(
        answers={
            a.question_key: _answer_value(a) for a in response.answers.all()
        },
        has_responded=True,
        submitted_at=response.submitted_at.isoformat(),
    )


@router.get(
    "/{campaign_id}/context",
    response={200: MemberContextSchema, 404: dict},
    auth=AuthBearer(),
    summary="Autofilled member context for the fill-out screen.",
)
def get_context(request, campaign_id: int):
    if not SurveyCampaign.objects.filter(pk=campaign_id).exists():
        return 404, {"detail": "Campaign not found."}
    return 200, MemberContextSchema(**build_member_context(request.user))


@router.get(
    "/{campaign_id}/questions",
    response={200: SurveyQuestionsSchema, 404: dict},
    auth=AuthBearer(),
)
def get_questions(request, campaign_id: int):
    campaign = SurveyCampaign.objects.filter(pk=campaign_id).first()
    if not campaign:
        return 404, {"detail": "Campaign not found."}
    definition = build_effective_definition(campaign)
    if not definition:
        return 404, {"detail": "Survey definition not found."}

    status = community_status(request.user)
    visible_defn_blocks = [
        b for b in definition.blocks if _block_visible(b, status)
    ]
    m_blocks = [serialize_block(b) for b in visible_defn_blocks]
    _inject_dynamic_rows(definition, m_blocks)
    _inject_context(definition, m_blocks)
    _filter_rows_by_usage(definition, m_blocks, request.user)
    return 200, SurveyQuestionsSchema(
        campaign_id=campaign.pk,
        definition_key=definition.key,
        title=definition.title,
        member_blocks=m_blocks,
    )


def _block_visible(block, status: str) -> bool:
    """Audience-gated blocks (e.g. onboarding) show only to matching status."""
    audience = getattr(block, "audience", "")
    if not audience:
        return True
    return status == audience


def _inject_dynamic_rows(definition, blocks):
    """Fill matrix rows that are sourced from live platform data (e.g. tribes)."""
    qmap = definition.question_map()
    for block in blocks:
        for question in block.questions:
            source = getattr(qmap.get(question.key), "row_source", "")
            if source:
                question.rows = resolve_dynamic_rows(source)


def _inject_context(definition, blocks):
    """Attach live display context (recent fleets + FCs) to content questions."""
    qmap = definition.question_map()
    for block in blocks:
        for question in block.questions:
            source = getattr(qmap.get(question.key), "context_source", "")
            if source:
                question.context = resolve_context(source)


def _filter_rows_by_usage(definition, blocks, user):
    """Drop matrix rows a member hasn't interacted with (only tools they use)."""
    qmap = definition.question_map()
    visible = None
    for block in blocks:
        for question in block.questions:
            if (
                getattr(qmap.get(question.key), "row_filter", "")
                != "service_usage"
            ):
                continue
            if visible is None:
                visible = visible_service_keys(user)
            question.rows = [
                r for r in question.rows if r.get("key") in visible
            ]


def _store_answer(response: SurveyResponse, question, value):
    """Persist one answer, typed according to the question definition."""
    fields = {
        "numeric_value": None,
        "text_value": "",
        "choice_value": "",
        "json_value": None,
    }
    if value is None:
        return
    if question.is_numeric():
        try:
            fields["numeric_value"] = float(value)
        except (TypeError, ValueError):
            return
    elif question.is_matrix():
        if isinstance(value, dict):
            fields["json_value"] = value
        else:
            return
    elif question.allows_multiple():
        fields["json_value"] = (
            list(value) if isinstance(value, (list, tuple)) else [value]
        )
    elif question.is_choice():
        fields["choice_value"] = str(value)
    else:  # text
        fields["text_value"] = str(value)

    SurveyAnswer.objects.update_or_create(
        response=response, question_key=question.key, defaults=fields
    )


@router.post(
    "/{campaign_id}/responses",
    response={200: SubmitResult, 400: dict, 404: dict},
    auth=AuthBearer(),
    summary="Submit (or update) the member's response. Idempotent per user.",
)
def post_response(request, campaign_id: int, payload: SubmitResponseRequest):
    campaign = SurveyCampaign.objects.filter(pk=campaign_id).first()
    if not campaign:
        return 404, {"detail": "Campaign not found."}
    if campaign.status != STATUS_OPEN:
        return 400, {"detail": "This survey is not open for responses."}
    if community_status(request.user) == "on_leave":
        return 400, {"detail": "Members on leave can't fill out the survey."}
    definition = build_effective_definition(campaign)
    if not definition:
        return 404, {"detail": "Survey definition not found."}
    qmap = definition.question_map()

    context = build_member_context(request.user)
    # Apply local corrections (stored on the response only, never written back).
    corrections = payload.context_corrections or {}
    context.update({k: v for k, v in corrections.items() if k in context})
    seg = build_segmentation(request.user, context)

    with transaction.atomic():
        response, _ = SurveyResponse.objects.update_or_create(
            campaign=campaign,
            user=request.user,
            defaults={
                "corporation_id": seg["corporation_id"],
                "corporation_name": seg["corporation_name"] or "",
                "tribe_names": seg["tribe_names"],
                "prime_time": seg["prime_time"] or "",
                "tenure_days": seg["tenure_days"],
                "tenure_cohort": seg["tenure_cohort"] or "",
                "activity_tier": seg["activity_tier"] or "",
                "role_flags": seg["role_flags"],
                "context_snapshot": context,
            },
        )
        for item in payload.answers:
            question = qmap.get(item.question_key)
            if not question:
                continue
            # An explicitly empty value means the member cleared the field on
            # edit — drop the stored answer so the saved response mirrors the
            # form exactly (WYSIWYG). Omitted keys are left untouched.
            if item.value in (None, "", [], {}):
                SurveyAnswer.objects.filter(
                    response=response, question_key=question.key
                ).delete()
            else:
                _store_answer(response, question, item.value)

    return 200, SubmitResult(
        ok=True, response_id=response.pk, detail="Response saved."
    )


@router.get(
    "/{campaign_id}/giveback",
    response={200: GivebackSchema, 404: dict},
    auth=AuthBearer(),
)
def get_giveback(request, campaign_id: int):
    campaign = SurveyCampaign.objects.filter(pk=campaign_id).first()
    if not campaign:
        return 404, {"detail": "Campaign not found."}
    return 200, GivebackSchema(**build_giveback_card(request.user, campaign))


@router.get(
    "/{campaign_id}/changelog",
    response={200: list, 404: dict},
    auth=AuthBearer(),
    summary="Published 'You said → We did' entries for this campaign.",
)
def get_changelog(request, campaign_id: int):
    campaign = SurveyCampaign.objects.filter(pk=campaign_id).first()
    if not campaign:
        return 404, {"detail": "Campaign not found."}
    entries = campaign.changelog_entries.filter(published=True)
    return 200, [
        ChangelogEntrySchema(
            heading=e.heading,
            body_markdown=e.body_markdown,
            sort_order=e.sort_order,
        ).dict()
        for e in entries
    ]
