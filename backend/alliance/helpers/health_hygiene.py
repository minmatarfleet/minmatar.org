"""Trial / leave / attention hygiene inputs for the alliance health snapshot."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, Optional

from django.contrib.auth.models import User
from django.db.models import Max, Sum

from alliance.helpers.hygiene import assemble_hygiene
from applications.models import EveCorporationApplication
from discord.models import DiscordChannelActivityRecord
from eveonline.models import (
    EveCharacter,
    EveCharacterCorporationHistory,
    EveCorporation,
)
from groups.models import (
    UserAffiliation,
    UserCommunityStatus,
    UserCommunityStatusHistory,
)


def compute_hygiene_payload(  # noqa: C901
    *,
    now: datetime,
    roster_user_ids: set[int],
    usernames: dict[int, str],
    display_name: dict[int, str],
    primary_corp: dict[int, int],
    primary_character: dict[int, int],
    corp_by_id: dict[int, dict[str, Any]],
    corp_ids: list[int],
    user_eves: dict[int, set[int]],
    status_of: Callable[[int], str],
    fleets_90d: dict[int, int],
    fleets_30d: dict[int, int],
    fleets_180_times: dict[int, list[datetime]],
    kills_90d: dict[int, int],
    kills_30d: dict[int, int],
    kills_small_90d: dict[int, int],
    last_fleet_at: dict[int, datetime],
    last_kill_at: dict[int, datetime],
    hygiene_since: datetime,
    hygiene_recent: datetime,
    hygiene_180: datetime,
    alliance_id: int,
    exempt_auth_groups: frozenset[str],
    restore_grace_days: int,
    corp_display_name: Callable[[dict], str],
) -> dict[str, Any]:
    """Build trial/leave hygiene section for the health snapshot."""
    trial_user_ids = {
        uid
        for uid in roster_user_ids
        if status_of(uid) == UserCommunityStatus.STATUS_TRIAL
    }
    active_user_ids = {
        uid
        for uid in roster_user_ids
        if status_of(uid) == UserCommunityStatus.STATUS_ACTIVE
    }
    on_leave_user_ids = {
        uid
        for uid in roster_user_ids
        if status_of(uid) == UserCommunityStatus.STATUS_ON_LEAVE
    }
    hygiene_uids = trial_user_ids | active_user_ids | on_leave_user_ids

    voice_hours_90d: dict[int, float] = {}
    voice_hours_30d: dict[int, float] = {}
    last_voice_at: dict[int, datetime] = {}
    username_to_uid = {name: uid for uid, name in usernames.items()}
    hygiene_usernames = [
        usernames[uid] for uid in hygiene_uids if uid in usernames
    ]
    if hygiene_usernames:
        voice_totals = {
            row["username"]: int(row["total"] or 0)
            for row in (
                DiscordChannelActivityRecord.objects.filter(
                    username__in=hygiene_usernames,
                    activity_type=DiscordChannelActivityRecord.VOICE_MINUTE,
                    created_on__gte=hygiene_since,
                )
                .values("username")
                .annotate(total=Sum("quantity"))
            )
        }
        voice_recent = {
            row["username"]: int(row["total"] or 0)
            for row in (
                DiscordChannelActivityRecord.objects.filter(
                    username__in=hygiene_usernames,
                    activity_type=DiscordChannelActivityRecord.VOICE_MINUTE,
                    created_on__gte=hygiene_recent,
                )
                .values("username")
                .annotate(total=Sum("quantity"))
            )
        }
        voice_latest = {
            row["username"]: row["latest"]
            for row in (
                DiscordChannelActivityRecord.objects.filter(
                    username__in=hygiene_usernames,
                    activity_type=DiscordChannelActivityRecord.VOICE_MINUTE,
                    created_on__gte=hygiene_since,
                )
                .values("username")
                .annotate(latest=Max("created_on"))
            )
            if row["latest"] is not None
        }
        for uname, minutes in voice_totals.items():
            uid = username_to_uid.get(uname)
            if uid is None:
                continue
            voice_hours_90d[uid] = round(minutes / 60, 1)
            voice_hours_30d[uid] = round(voice_recent.get(uname, 0) / 60, 1)
            latest = voice_latest.get(uname)
            if latest is not None:
                last_voice_at[uid] = latest

    days_since_activity: dict[int, Optional[int]] = {}
    for uid in hygiene_uids:
        times = [
            t
            for t in (
                last_fleet_at.get(uid),
                last_kill_at.get(uid),
                last_voice_at.get(uid),
            )
            if t is not None
        ]
        if times:
            days_since_activity[uid] = (now - max(times)).days
        else:
            days_since_activity[uid] = None

    alliance_corp_ids = set(corp_ids)
    char_rows = list(
        EveCharacter.objects.filter(
            user_id__in=hygiene_uids, character_id__isnull=False
        ).values_list("id", "user_id", "corporation_id")
    )
    char_ids = [row[0] for row in char_rows]
    hist_by_char: dict[int, list[tuple]] = defaultdict(list)
    if char_ids:
        for character_pk, corporation_id, start_date, hist_alliance_id in (
            EveCharacterCorporationHistory.objects.filter(
                character_id__in=char_ids
            )
            .order_by("character_id", "start_date", "record_id")
            .values_list(
                "character_id", "corporation_id", "start_date", "alliance_id"
            )
        ):
            hist_by_char[character_pk].append(
                (start_date, corporation_id, hist_alliance_id)
            )

    def is_alliance_corp(corporation_id, hist_alliance_id) -> bool:
        if corporation_id in alliance_corp_ids:
            return True
        return hist_alliance_id == alliance_id

    def current_stint_start(character_pk, current_corp_id):
        if current_corp_id not in alliance_corp_ids:
            return None
        rows = hist_by_char.get(character_pk, [])
        if not rows:
            return None
        stint_start = None
        for start_date, corporation_id, hist_alliance_id in reversed(rows):
            if is_alliance_corp(corporation_id, hist_alliance_id):
                stint_start = start_date
                continue
            break
        return stint_start

    alliance_starts: dict[int, datetime] = {}
    for character_pk, uid, corporation_id in char_rows:
        start = current_stint_start(character_pk, corporation_id)
        if start is None:
            continue
        prev = alliance_starts.get(uid)
        if prev is None or start < prev:
            alliance_starts[uid] = start
    alliance_days: dict[int, int] = {
        uid: (now - start).days for uid, start in alliance_starts.items()
    }

    accept_first: dict[int, datetime] = {}
    for uid, updated_at in EveCorporationApplication.objects.filter(
        user_id__in=trial_user_ids,
        status="accepted",
        corporation_id__in=alliance_corp_ids,
    ).values_list("user_id", "updated_at"):
        if updated_at is None:
            continue
        prev = accept_first.get(uid)
        if prev is None or updated_at < prev:
            accept_first[uid] = updated_at
    for uid, updated_at in accept_first.items():
        if uid not in alliance_days:
            alliance_days[uid] = (now - updated_at).days

    trial_started: dict[int, datetime] = {}
    for uid, changed_at in (
        UserCommunityStatusHistory.objects.filter(
            user_id__in=trial_user_ids,
            to_status=UserCommunityStatus.STATUS_TRIAL,
        )
        .order_by("user_id", "-changed_at")
        .values_list("user_id", "changed_at")
    ):
        if uid not in trial_started and changed_at is not None:
            trial_started[uid] = changed_at
    for uid, changed_at in trial_started.items():
        if uid not in alliance_days:
            alliance_days[uid] = (now - changed_at).days

    affiliation_meta: dict[int, dict[str, Any]] = {}
    for ua in UserAffiliation.objects.filter(
        user_id__in=trial_user_ids | active_user_ids
    ).select_related("affiliation"):
        affiliation_meta[ua.user_id] = {
            "affiliation": ua.affiliation.name,
            "requires_trial": bool(ua.affiliation.requires_trial),
        }

    exempt_labels: dict[int, list[str]] = defaultdict(list)
    for uid, gname in User.objects.filter(id__in=active_user_ids).values_list(
        "id", "groups__name"
    ):
        if not gname:
            continue
        if gname in exempt_auth_groups:
            exempt_labels[uid].append(gname)
        elif "Director" in gname and (
            "Corp" in gname
            or "Corporation" in gname
            or gname.endswith("Director")
        ):
            exempt_labels[uid].append(gname)
    for corp in EveCorporation.objects.filter(
        corporation_id__in=corp_ids
    ).prefetch_related("directors"):
        for director in corp.directors.all():
            if director.user_id and director.user_id in active_user_ids:
                exempt_labels[director.user_id].append(
                    "EveCorporation.directors"
                )
    exempt_str = {
        uid: ", ".join(dict.fromkeys(labels))
        for uid, labels in exempt_labels.items()
        if labels
    }

    restore_since = now - timedelta(days=restore_grace_days)
    restored_from_leave_at: dict[int, Optional[str]] = {}
    for uid, changed_at in (
        UserCommunityStatusHistory.objects.filter(
            user_id__in=active_user_ids,
            changed_at__gte=restore_since,
            from_status=UserCommunityStatus.STATUS_ON_LEAVE,
        )
        .exclude(to_status=UserCommunityStatus.STATUS_ON_LEAVE)
        .order_by("user_id", "-changed_at")
        .values_list("user_id", "changed_at")
    ):
        if uid not in restored_from_leave_at and changed_at is not None:
            restored_from_leave_at[uid] = changed_at.strftime("%Y-%m-%d")

    rejoin_grace: set[int] = set()
    for uid in active_user_ids:
        times = fleets_180_times.get(uid, [])
        in_90 = [jt for jt in times if jt >= hygiene_since]
        in_30_180 = [jt for jt in times if hygiene_180 <= jt < hygiene_recent]
        first_90 = min(in_90) if in_90 else None
        if (
            first_90 is not None
            and first_90 >= hygiene_recent
            and not in_30_180
        ):
            rejoin_grace.add(uid)

    linked_character_count = {
        uid: len(user_eves.get(uid, ())) for uid in hygiene_uids
    }

    return assemble_hygiene(
        trial_user_ids=trial_user_ids,
        active_user_ids=active_user_ids,
        on_leave_user_ids=on_leave_user_ids,
        usernames=usernames,
        display_name=display_name,
        primary_corp=primary_corp,
        primary_character=primary_character,
        corp_by_id=corp_by_id,
        linked_character_count=linked_character_count,
        fleets_90d=fleets_90d,
        fleets_30d=fleets_30d,
        kills_90d=kills_90d,
        kills_30d=kills_30d,
        kills_small_90d=kills_small_90d,
        voice_hours_90d=voice_hours_90d,
        voice_hours_30d=voice_hours_30d,
        days_since_activity=days_since_activity,
        alliance_days=alliance_days,
        affiliation_meta=affiliation_meta,
        exempt_labels=exempt_str,
        restored_from_leave_at=restored_from_leave_at,
        rejoin_grace=rejoin_grace,
        corp_display_name=corp_display_name,
    )
