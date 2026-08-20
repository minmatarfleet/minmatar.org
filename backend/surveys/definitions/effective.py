"""Merge a campaign's ad-hoc "spotlight" questions (stored as JSON on the
campaign) into its code-defined survey, as a block rendered just before the
Open floor. Returns a SurveyDefinition so every consumer (render, submit,
aggregation) treats spotlight questions like any other."""

import logging

from surveys.constants import (
    TYPE_AGREE,
    TYPE_ENPS,
    TYPE_MATRIX,
    TYPE_MULTI,
    TYPE_SCALE5,
    TYPE_SINGLE,
    TYPE_TEXT,
)
from surveys.definitions.registry import get_definition
from surveys.definitions.types import Block, Question, SurveyDefinition

logger = logging.getLogger(__name__)

_ALLOWED_TYPES = {
    TYPE_SCALE5,
    TYPE_ENPS,
    TYPE_AGREE,
    TYPE_SINGLE,
    TYPE_MULTI,
    TYPE_TEXT,
    TYPE_MATRIX,
}


def _question_from_dict(d: dict) -> Question | None:
    try:
        key = d.get("key")
        qtype = d.get("type")
        if not key or qtype not in _ALLOWED_TYPES:
            return None
        return Question(
            key=f"spotlight.{key}",
            type=qtype,
            label=d.get("label", ""),
            help=d.get("help", ""),
            choices=tuple(d.get("choices", []) or ()),
            required=bool(d.get("required", False)),
            scale_kind=d.get("scale_kind", "") or "",
        )
    except Exception:  # pragma: no cover - defensive
        logger.debug("bad spotlight question: %r", d, exc_info=True)
        return None


def build_effective_definition(campaign) -> SurveyDefinition | None:
    base = get_definition(campaign.definition_key)
    if not base:
        return None
    raw = getattr(campaign, "spotlight_questions", None) or []
    questions = tuple(
        q for q in (_question_from_dict(d) for d in raw) if q is not None
    )
    if not questions:
        return base

    spotlight_block = Block(
        key="spotlight",
        title="A few extra questions",
        description="A couple of one-off questions just for this survey.",
        questions=questions,
    )

    blocks: list[Block] = []
    inserted = False
    for b in base.blocks:
        # Insert just before the Open floor.
        if not inserted and b.key == "open":
            blocks.append(spotlight_block)
            inserted = True
        blocks.append(b)
    if not inserted:
        blocks.append(spotlight_block)

    return SurveyDefinition(
        key=base.key, title=base.title, blocks=tuple(blocks)
    )
