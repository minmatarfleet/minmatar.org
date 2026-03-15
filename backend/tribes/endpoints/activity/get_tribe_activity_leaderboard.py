"""GET /{tribe_id}/activity/leaderboard - paginated leaderboard (points only)."""

from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.db.models import ExpressionWrapper, F, FloatField, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from ninja import Router, Query

from eveonline.helpers.characters import (
    user_characters,
    user_primary_character,
)
from eveonline.models import EvePlayer
from tribes.endpoints.groups.schemas import (
    CharacterRefSchema,
    TribeActivityLeaderboardEntrySchema,
    TribeActivityLeaderboardListSchema,
)
from tribes.helpers import user_is_tribe_chief
from tribes.models import Tribe, TribeGroupActivityRecord

PATH = "/{tribe_id}/activity/leaderboard"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Paginated leaderboard by total points; points only.",
    "response": {200: TribeActivityLeaderboardListSchema, 404: dict},
}

router = Router(tags=["Tribes - Activity"])

MAX_LIMIT = 100
DEFAULT_LIMIT = 50


def _parse_since_until(since: str | None, until: str | None):
    start = end = None
    if since:
        try:
            if since.endswith("d"):
                start = timezone.now() - timedelta(days=int(since[:-1]))
            else:
                start = datetime.fromisoformat(since.replace("Z", "+00:00"))
                if timezone.is_naive(start):
                    start = timezone.make_aware(start)
        except (ValueError, TypeError):
            pass
    if until:
        try:
            end = datetime.fromisoformat(until.replace("Z", "+00:00"))
            if timezone.is_naive(end):
                end = timezone.make_aware(end)
        except (ValueError, TypeError):
            pass
    return start, end


def _primary_by_user(user_ids):
    """Return dict user_id -> (character_id, character_name) from EvePlayer.primary_character."""
    players = (
        EvePlayer.objects.filter(user_id__in=user_ids)
        .select_related("primary_character")
        .only(
            "user_id",
            "primary_character_id",
            "primary_character__character_id",
            "primary_character__character_name",
        )
    )
    result = {}
    for p in players:
        if p.primary_character_id:
            result[p.user_id] = (
                p.primary_character.character_id,
                p.primary_character.character_name or "",
            )
    return result


def _alts_by_user(user_ids):
    """Return dict user_id -> list of CharacterRefSchema (non-primary characters)."""
    user_model = get_user_model()
    users = {u.pk: u for u in user_model.objects.filter(pk__in=user_ids)}
    result = {}
    for user_id in user_ids:
        user = users.get(user_id)
        if not user:
            result[user_id] = []
            continue
        primary = user_primary_character(user)
        chars = user_characters(user)
        result[user_id] = [
            CharacterRefSchema(
                character_id=c.character_id,
                character_name=c.character_name or "",
            )
            for c in chars
            if not primary or c.pk != primary.pk
        ]
    return result


def _build_leaderboard_items(
    user_ids, primary_by_user, alts_by_user, points_by_user, include_alts
):
    """Build list of TribeActivityLeaderboardEntrySchema for the given user_ids."""
    items = []
    for user_id in user_ids:
        primary = primary_by_user.get(user_id)
        pc_id, pc_name = primary if primary else (None, "")
        alts = alts_by_user.get(user_id, []) if include_alts else []
        items.append(
            TribeActivityLeaderboardEntrySchema(
                user_id=user_id,
                primary_character_id=pc_id,
                primary_character_name=pc_name,
                alts=alts,
                total_points=points_by_user.get(user_id, 0.0),
            )
        )
    return items


def get_tribe_activity_leaderboard(
    request,
    tribe_id: int,
    group_id: int | None = Query(None),
    activity_type: str | None = Query(None),
    since: str | None = Query(None),
    until: str | None = Query(None),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
    order: str = Query("total_points"),
):
    tribe = Tribe.objects.filter(pk=tribe_id).first()
    if not tribe:
        return 404, {"detail": "Tribe not found."}

    can_view_members = user_is_tribe_chief(request.user, tribe)

    qs = TribeGroupActivityRecord.objects.filter(
        tribe_group_activity__tribe_group__tribe_id=tribe_id
    ).filter(user_id__isnull=False)

    if group_id is not None:
        qs = qs.filter(tribe_group_activity__tribe_group_id=group_id)
    if activity_type:
        qs = qs.filter(tribe_group_activity__activity_type=activity_type)
    start, end = _parse_since_until(since, until)
    if start:
        qs = qs.filter(created_at__gte=start)
    if end:
        qs = qs.filter(created_at__lte=end)

    points_expr = ExpressionWrapper(
        Coalesce(F("tribe_group_activity__points_per_record"), Value(0.0))
        + Coalesce(F("tribe_group_activity__points_per_unit"), Value(0.0))
        * Coalesce(F("quantity"), Value(0.0)),
        output_field=FloatField(),
    )
    qs = (
        qs.values("user_id")
        .annotate(total_points=Sum(points_expr))
        .order_by("-total_points")
    )
    total = qs.count()
    page = list(qs[offset : offset + limit])
    if not page:
        return 200, TribeActivityLeaderboardListSchema(
            items=[], total=total, limit=limit, offset=offset
        )

    user_ids = [r["user_id"] for r in page]
    points_by_user = {r["user_id"]: float(r["total_points"]) for r in page}

    primary_by_user = _primary_by_user(user_ids)
    alts_by_user = _alts_by_user(user_ids) if can_view_members else {}
    items = _build_leaderboard_items(
        user_ids,
        primary_by_user,
        alts_by_user,
        points_by_user,
        can_view_members,
    )

    return 200, TribeActivityLeaderboardListSchema(
        items=items, total=total, limit=limit, offset=offset
    )


router.get(PATH, **ROUTE_SPEC)(get_tribe_activity_leaderboard)
