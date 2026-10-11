"""Convert code definitions and ORM rows into API schemas."""

from surveys.definitions.types import Block, Question
from surveys.endpoints.schemas import (
    BlockSchema,
    CampaignSchema,
    QuestionSchema,
)


def serialize_question(q: Question) -> QuestionSchema:
    return QuestionSchema(
        key=q.key,
        type=q.type,
        label=q.label,
        help=q.help,
        choices=list(q.choices),
        rows=[{"key": r[0], "label": r[1]} for r in q.rows],
        required=q.required,
        trendable=q.trendable,
        group=q.group,
        scale_labels=list(q.scale_labels) if q.scale_labels else None,
        scale_kind=q.scale_kind,
    )


def serialize_block(b: Block) -> BlockSchema:
    return BlockSchema(
        key=b.key,
        title=b.title,
        description=b.description,
        questions=[serialize_question(q) for q in b.questions],
    )


def serialize_campaign(campaign) -> CampaignSchema:
    return CampaignSchema(
        id=campaign.pk,
        year=campaign.year,
        quarter=campaign.quarter,
        definition_key=campaign.definition_key,
        title=campaign.title,
        status=campaign.status,
        opens_at=campaign.opens_at.isoformat() if campaign.opens_at else None,
        closes_at=(
            campaign.closes_at.isoformat() if campaign.closes_at else None
        ),
        response_count=campaign.responses.count(),
    )
