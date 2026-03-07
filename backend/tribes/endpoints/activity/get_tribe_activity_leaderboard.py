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
from tribes.models import Tribe

from tribes.endpoints.groups.schemas import (
    CharacterRefSchema,
    TribeActivityLeaderboardEntrySchema,
    TribeActivityLeaderboardListSchema,
)
from tribes.models import TribeGroupActivityRecord

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
    if not Tribe.objects.filter(pk=tribe_id).exists():
        return 404, {"detail": "Tribe not found."}

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
    primary_by_user = {}
    for p in players:
        if p.primary_character_id:
            primary_by_user[p.user_id] = (
                p.primary_character.character_id,
                p.primary_character.character_name or "",
            )

    user_model = get_user_model()
    users = {u.pk: u for u in user_model.objects.filter(pk__in=user_ids)}
    alts_by_user = {}
    for user_id in user_ids:
        user = users.get(user_id)
        if not user:
            alts_by_user[user_id] = []
            continue
        primary = user_primary_character(user)
        chars = user_characters(user)
        alt_refs = [
            CharacterRefSchema(
                character_id=c.character_id,
                character_name=c.character_name or "",
            )
            for c in chars
            if not primary or c.pk != primary.pk
        ]
        alts_by_user[user_id] = alt_refs

    items = []
    for user_id in user_ids:
        primary = primary_by_user.get(user_id)
        if primary:
            pc_id, pc_name = primary
        else:
            pc_id, pc_name = None, ""
        items.append(
            TribeActivityLeaderboardEntrySchema(
                user_id=user_id,
                primary_character_id=pc_id,
                primary_character_name=pc_name,
                alts=alts_by_user.get(user_id, []),
                total_points=points_by_user.get(user_id, 0.0),
            )
        )

    return 200, TribeActivityLeaderboardListSchema(
        items=items, total=total, limit=limit, offset=offset
    )


router.get(PATH, **ROUTE_SPEC)(get_tribe_activity_leaderboard)
