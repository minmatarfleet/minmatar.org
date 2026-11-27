"""The exit survey form and its answers (design 07)."""

from dataclasses import replace

from django.db import transaction
from django.utils import timezone

from eveonline.models import (
    EveCharacter,
    EveCharacterCorporationHistory,
    EveCorporation,
)
from surveys.constants import NUMERIC_TYPES, TYPE_MULTI, TYPE_SINGLE, TYPE_TEXT
from surveys.definitions.exit import EXIT_DEFINITIONS
from surveys.endpoints.serializers import serialize_block
from surveys.models import (
    ExitSurveyAnswer,
    ExitSurveyInvite,
    ExitSurveyResponse,
)

MAX_TEXT = 4000
SCALE_RANGE = {"scale5": (1, 5), "agree": (1, 5), "enps": (0, 10)}


class ExitAnswerError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _names(invite: ExitSurveyInvite) -> dict:
    departure = invite.departure
    new_name = (
        EveCorporation.objects.filter(
            corporation_id=departure.destination_corporation_id
        )
        .values_list("name", flat=True)
        .first()
    )
    return {
        "corporation": departure.corporation.name,
        "new_corporation": new_name or "your new corporation",
        "new_corporation_name": new_name,
    }


def _labelled(definition, names):
    """The definition with {corporation} / {new_corporation} filled in."""
    blocks = []
    for block in definition.blocks:
        questions = tuple(
            replace(q, label=q.label.format(**names)) for q in block.questions
        )
        blocks.append(replace(block, questions=questions))
    return blocks


def survey_form(invite: ExitSurveyInvite) -> dict:
    departure = invite.departure
    definition = EXIT_DEFINITIONS[invite.definition_key]
    names = _names(invite)
    joined = (
        EveCharacterCorporationHistory.objects.filter(
            character__character_id=departure.character_id,
            corporation_id=departure.corporation.corporation_id,
            start_date__lte=departure.first_missing_at,
        )
        .order_by("-start_date")
        .values_list("start_date", flat=True)
        .first()
    )
    return {
        "definition_key": definition.key,
        "title": definition.title,
        "corporation_id": departure.corporation.corporation_id,
        "corporation_name": names["corporation"],
        "character_name": EveCharacter.objects.filter(
            character_id=departure.character_id
        )
        .values_list("character_name", flat=True)
        .first()
        or "",
        "member_from": joined,
        "member_to": departure.first_missing_at,
        "kind": departure.kind,
        "new_corporation_name": names["new_corporation_name"],
        "blocks": [serialize_block(b) for b in _labelled(definition, names)],
    }


def _clean(question, value):
    """The stored columns for one answer, or None when it's left empty."""
    if value in (None, "", []):
        return None
    if question.type in NUMERIC_TYPES:
        low, high = SCALE_RANGE.get(question.type, (1, 5))
        try:
            number = int(value)
        except (TypeError, ValueError) as exc:
            raise ExitAnswerError(f"{question.key} must be a number") from exc
        if not low <= number <= high:
            raise ExitAnswerError(f"{question.key} must be {low} to {high}")
        return {"numeric_value": number}
    if question.type == TYPE_MULTI:
        values = value if isinstance(value, list) else [value]
        picked = [str(v) for v in values if str(v) in question.choices]
        return {"json_value": picked} if picked else None
    if question.type == TYPE_SINGLE:
        if str(value) not in question.choices:
            return None
        return {"choice_value": str(value)}
    if question.type == TYPE_TEXT:
        text = str(value).strip()[:MAX_TEXT]
        return {"text_value": text} if text else None
    return None


def submit(invite: ExitSurveyInvite, answers: dict) -> ExitSurveyResponse:
    definition = EXIT_DEFINITIONS[invite.definition_key]
    cleaned = {}
    for question in definition.all_questions():
        columns = _clean(question, answers.get(question.key))
        if columns is not None:
            cleaned[question.key] = columns
    missing = [
        q.key
        for q in definition.all_questions()
        if q.required and q.key not in cleaned
    ]
    if missing:
        keys = ", ".join(missing)
        raise ExitAnswerError(f"Answer the required questions: {keys}")
    now = timezone.now()
    with transaction.atomic():
        locked = ExitSurveyInvite.objects.select_for_update().get(pk=invite.pk)
        if locked.responded_at is not None:
            raise ExitAnswerError("used")
        response = ExitSurveyResponse.objects.create(
            invite=locked,
            corporation_id=locked.departure.corporation.corporation_id,
            definition_key=locked.definition_key,
            definition_version=locked.definition_version,
            submitted_at=now,
        )
        ExitSurveyAnswer.objects.bulk_create(
            ExitSurveyAnswer(response=response, question_key=key, **columns)
            for key, columns in cleaned.items()
        )
        locked.responded_at = now
        locked.save(update_fields=["responded_at"])
    return response
