"""Public application pace and the reviewer queue for one corporation."""

from __future__ import annotations

from django.contrib.auth.models import User
from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

from applications.models import EveCorporationApplication
from eveonline.helpers.corporations.permissions import can_manage_corporation
from eveonline.models import EveCharacterSkill, EveCorporation, EvePlayer
from groups.helpers.feature_access import can_use_feature

DAYS_PER_MONTH = 30.4375
ACCEPTANCE_WINDOW_DAYS = 30


def can_review_applications(user: User, corporation: EveCorporation) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if can_manage_corporation(user, corporation):
        return True
    if corporation.recruiters.filter(user_id=user.id).exists():
        return True
    if corporation.recruiters.filter(token__user_id=user.id).exists():
        return True
    if can_use_feature(user, "applications.view"):
        return True
    return can_use_feature(user, "applications.manage")


def application_process(corporation_id: int) -> dict:
    applications = EveCorporationApplication.objects.filter(
        corporation_id=corporation_id
    )
    outstanding = applications.filter(status="pending").count()
    return {
        "outstanding": outstanding,
        "applications_per_month": _per_month(applications),
        "acceptance_days": _acceptance_days(applications),
        "average_skill_points": _average_skill_points(applications),
    }


def outstanding_applications(corporation_id: int) -> list[dict]:
    pending = list(
        EveCorporationApplication.objects.filter(
            corporation_id=corporation_id,
            status="pending",
        )
        .select_related("user")
        .order_by("created_at")
    )
    players = EvePlayer.objects.filter(
        user_id__in=[application.user_id for application in pending],
        primary_character__isnull=False,
    ).select_related("primary_character")
    primaries = {
        player.user_id: player.primary_character
        for player in players
        if player.primary_character is not None
    }
    rows = []
    for application in pending:
        character = primaries.get(application.user_id)
        rows.append(
            {
                "application_id": application.id,
                "character_id": (
                    character.character_id if character is not None else None
                ),
                "character_name": (
                    character.character_name
                    if character is not None
                    else application.user.username
                ),
                "created_at": application.created_at,
            }
        )
    return rows


def _per_month(applications) -> float | None:
    first = (
        applications.order_by("created_at")
        .values_list("created_at", flat=True)
        .first()
    )
    count = applications.count()
    if first is None or count == 0:
        return None
    days = max((timezone.now() - first).days, 1)
    months = max(days / DAYS_PER_MONTH, 1)
    return round(count / months, 1)


def _acceptance_days(applications) -> float | None:
    """Mean days from application to acceptance, over applications
    accepted in the last ``ACCEPTANCE_WINDOW_DAYS`` days.

    ``updated_at`` is the acceptance timestamp only for recent rows; older
    rows were bulk re-saved and would skew a lifetime average.
    """
    cutoff = timezone.now() - timedelta(days=ACCEPTANCE_WINDOW_DAYS)
    accepted = applications.filter(status="accepted", updated_at__gte=cutoff)
    spans = []
    for created_at, updated_at in accepted.values_list(
        "created_at", "updated_at"
    ):
        if created_at is None or updated_at is None:
            continue
        spans.append((updated_at - created_at).total_seconds())
    if not spans:
        return None
    return round((sum(spans) / len(spans)) / 86400, 1)


def _average_skill_points(applications) -> int | None:
    user_ids = list(applications.values_list("user_id", flat=True).distinct())
    if not user_ids:
        return None
    primary_ids = list(
        EvePlayer.objects.filter(
            user_id__in=user_ids,
            primary_character__isnull=False,
        ).values_list("primary_character_id", flat=True)
    )
    if not primary_ids:
        return None
    totals = (
        EveCharacterSkill.objects.filter(character_id__in=primary_ids)
        .values("character_id")
        .annotate(total=Sum("skill_points"))
    )
    values = [row["total"] for row in totals if row["total"]]
    if not values:
        return None
    return round(sum(values) / len(values))
