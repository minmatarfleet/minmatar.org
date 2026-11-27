"""A flagged pilot joining a tracked corporation (design 06, screen 4)."""

from datetime import datetime

from django.contrib.auth.models import User
from django.utils import timezone

from eveonline.helpers.corporations.permissions import (
    user_is_ceo,
    user_is_director,
)
from eveonline.models import EveCharacter, EveCorporation
from exits.helpers.answers import AnswerError, can_answer
from exits.helpers.history import active_flags_for
from exits.models import FlaggedJoin


def can_lead(user: User, corporation: EveCorporation) -> bool:
    """CEO, directors and superusers: who sees a member's alliance history."""
    return bool(
        user
        and (
            user.is_superuser
            or user_is_ceo(user, corporation)
            or user_is_director(user, corporation)
        )
    )


def record_flagged_joins(
    corporation: EveCorporation, joined_ids: set[int], now: datetime
) -> int:
    if not joined_ids:
        return 0
    users = dict(
        EveCharacter.objects.filter(character_id__in=joined_ids).values_list(
            "character_id", "user_id"
        )
    )
    user_objects = User.objects.in_bulk([u for u in users.values() if u])
    already = set(
        FlaggedJoin.objects.filter(
            corporation=corporation, outcome="", character_id__in=joined_ids
        ).values_list("character_id", flat=True)
    )
    created = 0
    for character_id in sorted(joined_ids - already):
        user = user_objects.get(users.get(character_id))
        flags = active_flags_for(user, [character_id])
        if not flags:
            continue
        FlaggedJoin.objects.create(
            corporation=corporation,
            character_id=character_id,
            user=user,
            flag_ids=[flag.pk for flag in flags],
            seen_at=now,
        )
        created += 1
    return created


def resolve_removed(corporation: EveCorporation, member_ids: set[int]) -> int:
    """Open joins whose pilot is no longer in the corporation are done."""
    return (
        FlaggedJoin.objects.filter(corporation=corporation, outcome="")
        .exclude(character_id__in=member_ids)
        .update(
            outcome=FlaggedJoin.OUTCOME_REMOVED, resolved_at=timezone.now()
        )
    )


def _open_join(by: User, join: FlaggedJoin) -> None:
    if not can_answer(by, join.corporation):
        raise AnswerError("Only the corporation's CEO can answer this", 403)
    if join.outcome:
        raise AnswerError("This has already been answered", 409)


def keep(by: User, join: FlaggedJoin, note: str) -> FlaggedJoin:
    _open_join(by, join)
    note = (note or "").strip()
    if not note:
        raise AnswerError("Say why you're keeping them")
    join.outcome = FlaggedJoin.OUTCOME_KEPT
    join.note = note
    join.resolved_by = by
    join.resolved_at = timezone.now()
    join.save(update_fields=["outcome", "note", "resolved_by", "resolved_at"])
    return join


def expect_removal(by: User, join: FlaggedJoin) -> FlaggedJoin:
    _open_join(by, join)
    join.removal_expected_at = timezone.now()
    join.resolved_by = by
    join.save(update_fields=["removal_expected_at", "resolved_by"])
    return join
