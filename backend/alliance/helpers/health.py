"""Alliance health rollup — MAP, quiet pilots, corps, cohorts, hygiene.

Unit: site User with ≥1 linked character currently in an MFA alliance corp.
Active signals (no Discord voice): fleet attendance, killmail attack
(solo / small-gang / other), supply (mining, PI, industry jobs/assignments,
freight, LP market, buyback). Trial/leave hygiene also uses Discord voice.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Optional

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import User
from django.db.models import Count, F, Max, Q, Sum
from django.utils import timezone

from alliance.helpers.hygiene import assemble_hygiene
from alliance.models import AllianceHealthSnapshot
from applications.models import EveCorporationApplication
from buyback.models import BuybackContract
from discord.models import DiscordChannelActivityRecord
from eveonline.models import (
    EveCharacter,
    EveCharacterCorporationHistory,
    EveCharacterIndustryJob,
    EveCharacterKillmailAttacker,
    EveCharacterMiningEntry,
    EveCharacterPlanet,
    EveCorporation,
    EvePlayer,
)
from fleets.models import EveFleetInstanceMember
from freight.models import FreightContract
from groups.helpers import PEOPLE_TEAM, TECH_TEAM, TRIBE_CHIEF_GROUP_NAME
from groups.models import (
    UserAffiliation,
    UserCommunityStatus,
    UserCommunityStatusHistory,
)
from industry.models import (
    IndustryLoyaltyPointMarketOrder,
    IndustryOrderItemAssignment,
)

ALLIANCE_ID = 99011978
ACADEMY_CORP_ID = 98741376
MH0LD_TICKER = "MH0LD"
GOAL_MAP = 500
HIST_MONTHS = 12
HYGIENE_DAYS = 90
HYGIENE_RECENT_DAYS = 30
RESTORE_GRACE_DAYS = 30
EXEMPT_AUTH_GROUPS = frozenset(
    {PEOPLE_TEAM, TECH_TEAM, TRIBE_CHIEF_GROUP_NAME}
)


def _aware(d: date) -> datetime:
    return timezone.make_aware(datetime.combine(d, datetime.min.time()))


def _month_key(dt: datetime | date) -> str:
    return f"{dt.year:04d}-{dt.month:02d}"


def _corp_display_name(corp: dict) -> str:
    if corp.get("corporation_id") == ACADEMY_CORP_ID:
        return "Minmatar Fleet Academy"
    return (
        corp.get("name")
        or corp.get("ticker")
        or str(corp.get("corporation_id"))
    )


def compute_alliance_health(  # noqa: C901
    now: datetime | None = None,
) -> dict[str, Any]:
    """Compute full alliance health payload (expensive — cache via snapshot)."""
    now = now or timezone.now()
    hist_start = (
        now.replace(day=1) - relativedelta(months=HIST_MONTHS)
    ).replace(hour=0, minute=0, second=0, microsecond=0)
    hist_date = hist_start.date()

    corps = list(
        EveCorporation.objects.filter(alliance__alliance_id=ALLIANCE_ID)
        .exclude(ticker=MH0LD_TICKER)
        .values("corporation_id", "name", "ticker", "member_count")
    )
    corp_by_id = {c["corporation_id"]: c for c in corps}
    corp_ids = list(corp_by_id)

    roster_rows = list(
        EveCharacter.objects.filter(
            corporation_id__in=corp_ids, user_id__isnull=False
        ).values_list(
            "user_id", "character_id", "id", "corporation_id", "character_name"
        )
    )
    user_eves: dict[int, set[int]] = defaultdict(set)
    user_pks: dict[int, set[int]] = defaultdict(set)
    user_corps: dict[int, set[int]] = defaultdict(set)
    eve_to_user: dict[int, int] = {}
    pk_to_user: dict[int, int] = {}
    # Prefer primary-char name later; seed with any roster char name
    display_name: dict[int, str] = {}
    for uid, eve_id, pk, corp_id, char_name in roster_rows:
        user_eves[uid].add(eve_id)
        user_pks[uid].add(pk)
        user_corps[uid].add(corp_id)
        eve_to_user[eve_id] = uid
        pk_to_user[pk] = uid
        if char_name and uid not in display_name:
            display_name[uid] = char_name

    roster_user_ids = set(user_eves)
    all_eves = list(eve_to_user)
    all_pks = list(pk_to_user)

    primary_corp: dict[int, int] = {}
    primary_character: dict[int, int] = {}
    for ep in EvePlayer.objects.filter(
        user_id__in=roster_user_ids, primary_character__isnull=False
    ).select_related("primary_character"):
        pc = ep.primary_character
        if pc is None:
            continue
        if pc.character_name:
            display_name[ep.user_id] = pc.character_name
        primary_character[ep.user_id] = pc.character_id
        if pc.corporation_id in corp_by_id:
            primary_corp[ep.user_id] = pc.corporation_id
    for uid, corps_set in user_corps.items():
        if uid not in primary_corp and corps_set:
            home = [c for c in corps_set if c != ACADEMY_CORP_ID]
            primary_corp[uid] = home[0] if home else next(iter(corps_set))
    for uid, eves in user_eves.items():
        if uid not in primary_character and eves:
            primary_character[uid] = next(iter(eves))

    status_by_user = {
        ucs.user_id: ucs.status
        for ucs in UserCommunityStatus.objects.filter(
            user_id__in=roster_user_ids
        )
    }

    def status_of(uid: int) -> str:
        return status_by_user.get(uid, UserCommunityStatus.STATUS_ACTIVE)

    status_counts: dict[str, int] = defaultdict(int)
    for uid in roster_user_ids:
        status_counts[status_of(uid)] += 1

    usernames = dict(
        User.objects.filter(id__in=roster_user_ids).values_list(
            "id", "username"
        )
    )
    for uid, uname in usernames.items():
        display_name.setdefault(uid, uname)

    # Events: (user_id, datetime, signal) — fleet | solo | small_gang | kill | supply
    events: list[tuple[int, datetime, str]] = []

    hygiene_since = now - timedelta(days=HYGIENE_DAYS)
    hygiene_recent = now - timedelta(days=HYGIENE_RECENT_DAYS)
    hygiene_180 = now - timedelta(days=180)
    fleets_90d_sets: dict[int, set[int]] = defaultdict(set)
    fleets_30d_sets: dict[int, set[int]] = defaultdict(set)
    fleets_180_times: dict[int, list[datetime]] = defaultdict(list)
    last_fleet_at: dict[int, datetime] = {}
    last_kill_at: dict[int, datetime] = {}
    kills_90d: dict[int, int] = defaultdict(int)
    kills_30d: dict[int, int] = defaultdict(int)
    kills_small_90d: dict[int, int] = defaultdict(int)

    for cid, jt, iid in (
        EveFleetInstanceMember.objects.filter(
            character_id__in=all_eves, join_time__gte=hist_start
        )
        .values_list("character_id", "join_time", "eve_fleet_instance_id")
        .iterator(chunk_size=10000)
    ):
        uid = eve_to_user.get(cid)
        if uid is None or jt is None:
            continue
        events.append((uid, jt, "fleet"))
        if jt >= hygiene_180:
            fleets_180_times[uid].append(jt)
        if jt >= hygiene_since and iid is not None:
            fleets_90d_sets[uid].add(iid)
            prev = last_fleet_at.get(uid)
            if prev is None or jt > prev:
                last_fleet_at[uid] = jt
            if jt >= hygiene_recent:
                fleets_30d_sets[uid].add(iid)

    # Killmail attacker counts for solo / small-gang bucketing
    kill_rows = list(
        EveCharacterKillmailAttacker.objects.filter(
            character_id__in=all_eves,
            killmail__killmail_time__gte=hist_start,
        )
        .exclude(character_id=F("killmail__victim_character_id"))
        .values_list("character_id", "killmail__killmail_time", "killmail_id")
        .iterator(chunk_size=10000)
    )
    km_ids = {row[2] for row in kill_rows if row[2] is not None}
    attacker_counts: dict[int, int] = {}
    if km_ids:
        for km_id, n in (
            EveCharacterKillmailAttacker.objects.filter(killmail_id__in=km_ids)
            .values("killmail_id")
            .annotate(n=Count("id"))
            .values_list("killmail_id", "n")
        ):
            attacker_counts[km_id] = n
    for cid, kt, km_id in kill_rows:
        uid = eve_to_user.get(cid)
        if uid is None or kt is None:
            continue
        n = attacker_counts.get(km_id, 1)
        if n == 1:
            sig = "solo"
        elif n <= 10:
            sig = "small_gang"
        else:
            sig = "kill"
        events.append((uid, kt, sig))
        if kt >= hygiene_since:
            kills_90d[uid] += 1
            if n <= 10:
                kills_small_90d[uid] += 1
            prev = last_kill_at.get(uid)
            if prev is None or kt > prev:
                last_kill_at[uid] = kt
            if kt >= hygiene_recent:
                kills_30d[uid] += 1

    # Supply signals
    for pk, d in (
        EveCharacterMiningEntry.objects.filter(
            character_id__in=all_pks, date__gte=hist_date
        )
        .values_list("character_id", "date")
        .iterator(chunk_size=10000)
    ):
        uid = pk_to_user.get(pk)
        if uid is not None and d is not None:
            events.append((uid, _aware(d), "supply"))

    for pk, sd in (
        EveCharacterIndustryJob.objects.filter(character_id__in=all_pks)
        .filter(
            Q(start_date__gte=hist_start) | Q(completed_date__gte=hist_start)
        )
        .values_list("character_id", "start_date")
        .iterator(chunk_size=10000)
    ):
        uid = pk_to_user.get(pk)
        if uid is not None and sd is not None and sd >= hist_start:
            events.append((uid, sd, "supply"))

    for pk, delivered_at in (
        IndustryOrderItemAssignment.objects.filter(
            character_id__in=all_pks, delivered_at__gte=hist_start
        )
        .values_list("character_id", "delivered_at")
        .iterator(chunk_size=5000)
    ):
        uid = pk_to_user.get(pk)
        if uid is not None and delivered_at is not None:
            events.append((uid, delivered_at, "supply"))

    for cid, dc in (
        FreightContract.objects.filter(
            Q(date_issued__gte=hist_start)
            | Q(date_completed__gte=hist_start)
            | Q(date_accepted__gte=hist_start)
        )
        .filter(Q(acceptor_id__in=all_eves) | Q(issuer_id__in=all_eves))
        .values_list("acceptor_id", "date_completed")
        .iterator(chunk_size=5000)
    ):
        uid = eve_to_user.get(cid) if cid else None
        if uid is not None and dc is not None and dc >= hist_start:
            events.append((uid, dc, "supply"))

    for issuer_id, issued, completed, accepted in (
        FreightContract.objects.filter(
            Q(date_issued__gte=hist_start)
            | Q(date_completed__gte=hist_start)
            | Q(date_accepted__gte=hist_start)
        )
        .filter(Q(acceptor_id__in=all_eves) | Q(issuer_id__in=all_eves))
        .values_list(
            "issuer_id", "date_issued", "date_completed", "date_accepted"
        )
        .iterator(chunk_size=5000)
    ):
        for eve_id, dt in (
            (issuer_id, issued),
            (issuer_id, accepted),
            (issuer_id, completed),
        ):
            uid = eve_to_user.get(eve_id) if eve_id else None
            if uid is not None and dt is not None and dt >= hist_start:
                events.append((uid, dt, "supply"))

    for uid, created_at, updated_at, completed_at in (
        IndustryLoyaltyPointMarketOrder.objects.filter(
            Q(created_at__gte=hist_start)
            | Q(updated_at__gte=hist_start)
            | Q(completed_at__gte=hist_start),
            created_by_id__in=roster_user_ids,
        )
        .values_list(
            "created_by_id", "created_at", "updated_at", "completed_at"
        )
        .iterator(chunk_size=5000)
    ):
        if uid is None:
            continue
        for dt in (created_at, updated_at, completed_at):
            if dt is not None and dt >= hist_start:
                events.append((uid, dt, "supply"))

    for issuer_id, issued, completed in (
        BuybackContract.objects.filter(
            Q(date_issued__gte=hist_start) | Q(date_completed__gte=hist_start),
            issuer_id__in=all_eves,
        )
        .values_list("issuer_id", "date_issued", "date_completed")
        .iterator(chunk_size=5000)
    ):
        uid = eve_to_user.get(issuer_id)
        if uid is None:
            continue
        for dt in (issued, completed):
            if dt is not None and dt >= hist_start:
                events.append((uid, dt, "supply"))

    for pk, last_update in (
        EveCharacterPlanet.objects.filter(
            character_id__in=all_pks, last_update__gte=hist_start
        )
        .values_list("character_id", "last_update")
        .iterator(chunk_size=5000)
    ):
        uid = pk_to_user.get(pk)
        if uid is not None and last_update is not None:
            events.append((uid, last_update, "supply"))

    map_signals = frozenset({"fleet", "solo", "small_gang", "kill", "supply"})

    def users_active(
        since: datetime,
        until: datetime | None = None,
        signal: str | None = None,
        signals: frozenset[str] | None = None,
    ) -> set[int]:
        out: set[int] = set()
        for uid, dt, sig in events:
            if signal is not None and sig != signal:
                continue
            if signals is not None and sig not in signals:
                continue
            if dt < since:
                continue
            if until is not None and dt >= until:
                continue
            out.add(uid)
        return out

    s7 = users_active(now - timedelta(days=7), signals=map_signals)
    s14 = users_active(now - timedelta(days=14), signals=map_signals)
    s30 = users_active(now - timedelta(days=30), signals=map_signals)
    s90 = users_active(now - timedelta(days=90), signals=map_signals)

    signals_30 = {
        "fleets": len(users_active(now - timedelta(days=30), signal="fleet")),
        "small_gang": len(
            users_active(now - timedelta(days=30), signal="small_gang")
        ),
        "solo": len(users_active(now - timedelta(days=30), signal="solo")),
        "supply": len(users_active(now - timedelta(days=30), signal="supply")),
    }

    # Last activity + active months for quiet / seasonal
    last_activity: dict[int, datetime] = {}
    months_active: dict[int, set[str]] = defaultdict(set)
    year_ago = now - relativedelta(years=1)
    for uid, dt, sig in events:
        if sig not in map_signals:
            continue
        prev = last_activity.get(uid)
        if prev is None or dt > prev:
            last_activity[uid] = dt
        if dt >= year_ago:
            months_active[uid].add(_month_key(dt))

    eligible = {uid for uid in roster_user_ids if status_of(uid) != "on_leave"}
    quiet_30 = eligible - s30
    fading = {
        uid for uid in quiet_30 if uid in s90
    }  # active in 90d, quiet 30d
    dark = quiet_30 - s90  # nothing in 90d
    seasonal = {
        uid for uid in quiet_30 if len(months_active.get(uid, ())) >= 3
    }

    def pilot_row(uid: int) -> dict[str, Any]:
        last = last_activity.get(uid)
        if last is None:
            days_quiet: int | str = "never"
        else:
            days_quiet = (now - last).days
        corp_id = primary_corp.get(uid)
        corp_meta = corp_by_id.get(corp_id) if corp_id else None
        return {
            "user_id": uid,
            "character_id": primary_character.get(uid),
            "corporation_id": corp_id,
            "pilot": display_name.get(uid, usernames.get(uid, str(uid))),
            "corp": _corp_display_name(corp_meta) if corp_meta else "—",
            "status": status_of(uid),
            "days_quiet": days_quiet,
            "active_months": len(months_active.get(uid, ())),
        }

    def sort_pilots(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        def key(r: dict[str, Any]):
            dq = r["days_quiet"]
            return (
                0 if dq == "never" else 1,
                -(dq if isinstance(dq, int) else 0),
                r["pilot"],
            )

        return sorted(rows, key=key)

    attention = {
        "fading": sort_pilots([pilot_row(uid) for uid in fading]),
        "dark": sort_pilots([pilot_row(uid) for uid in dark]),
        "seasonal": sort_pilots([pilot_row(uid) for uid in seasonal]),
    }

    quiet_counts = {
        "fading": len(fading),
        "dark": len(dark),
        "seasonal": len(seasonal),
    }

    # Monthly series (completed months only)
    monthly: list[dict[str, Any]] = []
    cur = hist_start.date().replace(day=1)
    this_month = now.date().replace(day=1)
    while cur < this_month:
        nxt = cur + relativedelta(months=1)
        since_dt = _aware(cur)
        until_dt = _aware(nxt)
        monthly.append(
            {
                "month": _month_key(cur),
                "label": (
                    cur.strftime("%b %y")
                    if cur.month == 1
                    or cur == hist_start.date().replace(day=1)
                    else cur.strftime("%b")
                ),
                "active": len(
                    users_active(since_dt, until_dt, signals=map_signals)
                ),
                "fleet": len(users_active(since_dt, until_dt, signal="fleet")),
                "solo": len(users_active(since_dt, until_dt, signal="solo")),
                "supply": len(
                    users_active(since_dt, until_dt, signal="supply")
                ),
            }
        )
        cur = nxt

    # Corp health — 90d active / growth
    prior_90_start = now - timedelta(days=180)
    prior_90_end = now - timedelta(days=90)
    s90_prior = users_active(prior_90_start, prior_90_end, signals=map_signals)

    corporations: list[dict[str, Any]] = []
    for cid, meta in sorted(
        corp_by_id.items(), key=lambda x: -(x[1].get("member_count") or 0)
    ):
        # ESI member_count may be stale; linked characters:
        linked_chars = EveCharacter.objects.filter(
            corporation_id=cid, user_id__isnull=False
        ).count()
        esi_chars = meta.get("member_count") or linked_chars
        humans = {
            uid for uid, corps_set in user_corps.items() if cid in corps_set
        }
        active_90 = humans & s90
        prior_active = humans & s90_prior
        rate = round(100 * len(active_90) / len(humans), 1) if humans else 0.0
        if prior_active:
            growth = round(
                100 * (len(active_90) - len(prior_active)) / len(prior_active),
                1,
            )
        elif active_90:
            growth = 100.0
        else:
            growth = 0.0
        corporations.append(
            {
                "corporation_id": cid,
                "name": _corp_display_name(meta),
                "characters": esi_chars,
                "humans": len(humans),
                "active_90d": len(active_90),
                "active_90d_pct": rate,
                "growth_90d_pct": growth,
            }
        )

    # Cohorts — applications + accepts per completed month
    all_apps = list(
        EveCorporationApplication.objects.filter(
            corporation_id__in=corp_ids
        ).values(
            "user_id", "corporation_id", "status", "created_at", "updated_at"
        )
    )

    # Fleet joins for cohort windows
    fleet_joins: dict[int, list[tuple[datetime, int]]] = defaultdict(list)
    app_user_ids = {a["user_id"] for a in all_apps}
    missing = app_user_ids - set(user_eves)
    if missing:
        for uid, eve_id in EveCharacter.objects.filter(
            user_id__in=missing, character_id__isnull=False
        ).values_list("user_id", "character_id"):
            user_eves[uid].add(eve_id)
            eve_to_user[eve_id] = uid
    cohort_eves = list(
        {eid for uid in app_user_ids for eid in user_eves.get(uid, ())}
    )
    if cohort_eves:
        for cid, jt, iid in (
            EveFleetInstanceMember.objects.filter(
                character_id__in=cohort_eves, join_time__gte=hist_start
            )
            .values_list("character_id", "join_time", "eve_fleet_instance_id")
            .iterator(chunk_size=10000)
        ):
            uid = eve_to_user.get(cid)
            if uid is not None and jt is not None:
                fleet_joins[uid].append((jt, iid))

    cohorts: list[dict[str, Any]] = []
    for m in reversed(monthly[-6:] if len(monthly) >= 6 else monthly):
        y, mo = map(int, m["month"].split("-"))
        m_start = timezone.make_aware(datetime(y, mo, 1))
        m_end = m_start + relativedelta(months=1)
        apps_created = [
            a
            for a in all_apps
            if a["created_at"] and m_start <= a["created_at"] < m_end
        ]
        accepts = [
            a
            for a in all_apps
            if a["status"] == "accepted"
            and a["updated_at"]
            and m_start <= a["updated_at"] < m_end
        ]
        user_seen: set[int] = set()
        week1 = with_1 = with_3 = academy_accepts = 0
        for a in accepts:
            uid = a["user_id"]
            if uid in user_seen:
                continue
            user_seen.add(uid)
            if a["corporation_id"] == ACADEMY_CORP_ID:
                academy_accepts += 1
            join_t = a["updated_at"]
            week_end = join_t + timedelta(days=7)
            month_end = join_t + timedelta(days=30)
            fleets_week = {
                iid
                for jt, iid in fleet_joins.get(uid, [])
                if join_t <= jt < week_end
            }
            fleets_30 = {
                iid
                for jt, iid in fleet_joins.get(uid, [])
                if join_t <= jt < month_end
            }
            if fleets_week:
                week1 += 1
            if len(fleets_30) >= 1:
                with_1 += 1
            if len(fleets_30) >= 3:
                with_3 += 1
        n = len(user_seen)
        # Unique applicants by created_at
        app_users = {a["user_id"] for a in apps_created}
        cohorts.append(
            {
                "month": m["month"],
                "label": m["label"],
                "applications": len(app_users),
                "accepts": n,
                "academy_accepts": academy_accepts,
                "fleet_first_week_pct": (
                    round(100 * week1 / n, 1) if n else 0.0
                ),
                "fleet_1_30d_pct": round(100 * with_1 / n, 1) if n else 0.0,
                "fleet_3_30d_pct": round(100 * with_3 / n, 1) if n else 0.0,
            }
        )

    return {
        "computed_at": now.isoformat(),
        "goal_map": GOAL_MAP,
        "map_7d": len(s7),
        "map_14d": len(s14),
        "map_30d": len(s30),
        "roster_people": len(roster_user_ids),
        "status": {
            "active": status_counts.get(UserCommunityStatus.STATUS_ACTIVE, 0),
            "trial": status_counts.get(UserCommunityStatus.STATUS_TRIAL, 0),
            "on_leave": status_counts.get(
                UserCommunityStatus.STATUS_ON_LEAVE, 0
            ),
        },
        "signals_30d": signals_30,
        "quiet": quiet_counts,
        "monthly": monthly,
        "attention": attention,
        "corporations": corporations,
        "cohorts": cohorts,
        "hygiene": _compute_hygiene_payload(
            now=now,
            roster_user_ids=roster_user_ids,
            usernames=usernames,
            display_name=display_name,
            primary_corp=primary_corp,
            primary_character=primary_character,
            corp_by_id=corp_by_id,
            corp_ids=corp_ids,
            user_eves=user_eves,
            status_of=status_of,
            fleets_90d={uid: len(s) for uid, s in fleets_90d_sets.items()},
            fleets_30d={uid: len(s) for uid, s in fleets_30d_sets.items()},
            fleets_180_times=fleets_180_times,
            kills_90d=dict(kills_90d),
            kills_30d=dict(kills_30d),
            kills_small_90d=dict(kills_small_90d),
            last_fleet_at=last_fleet_at,
            last_kill_at=last_kill_at,
            hygiene_since=hygiene_since,
            hygiene_recent=hygiene_recent,
            hygiene_180=hygiene_180,
        ),
    }


def _compute_hygiene_payload(  # noqa: C901
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
    status_of,
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
    hygiene_uids = trial_user_ids | active_user_ids

    # Discord voice (username-keyed)
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

    # Alliance tenure from corp history (current MFA stint)
    alliance_corp_ids = set(corp_ids)
    char_rows = list(
        EveCharacter.objects.filter(
            user_id__in=hygiene_uids, character_id__isnull=False
        ).values_list("id", "user_id", "corporation_id")
    )
    char_ids = [row[0] for row in char_rows]
    hist_by_char: dict[int, list[tuple]] = defaultdict(list)
    if char_ids:
        for character_pk, corporation_id, start_date, alliance_id in (
            EveCharacterCorporationHistory.objects.filter(
                character_id__in=char_ids
            )
            .order_by("character_id", "start_date", "record_id")
            .values_list(
                "character_id", "corporation_id", "start_date", "alliance_id"
            )
        ):
            hist_by_char[character_pk].append(
                (start_date, corporation_id, alliance_id)
            )

    def is_alliance_corp(corporation_id, alliance_id) -> bool:
        if corporation_id in alliance_corp_ids:
            return True
        return alliance_id == ALLIANCE_ID

    def current_stint_start(character_pk, current_corp_id):
        if current_corp_id not in alliance_corp_ids:
            return None
        rows = hist_by_char.get(character_pk, [])
        if not rows:
            return None
        stint_start = None
        for start_date, corporation_id, alliance_id in reversed(rows):
            if is_alliance_corp(corporation_id, alliance_id):
                stint_start = start_date
                continue
            break
        return stint_start

    # Earliest contiguous MFA join across linked chars = longest current tenure
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

    # Fallbacks: application accept, then trial status start
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

    # Affiliation meta for trials
    affiliation_meta: dict[int, dict[str, Any]] = {}
    for ua in UserAffiliation.objects.filter(
        user_id__in=trial_user_ids
    ).select_related("affiliation"):
        affiliation_meta[ua.user_id] = {
            "affiliation": ua.affiliation.name,
            "requires_trial": bool(ua.affiliation.requires_trial),
        }

    # Exempts: People/Tech/Chief + Corp Director auth groups + EveCorporation.directors
    exempt_labels: dict[int, list[str]] = defaultdict(list)
    for uid, gname in User.objects.filter(id__in=active_user_ids).values_list(
        "id", "groups__name"
    ):
        if not gname:
            continue
        if gname in EXEMPT_AUTH_GROUPS:
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

    # Restore grace
    restore_since = now - timedelta(days=RESTORE_GRACE_DAYS)
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

    # Rejoin grace: first 90d fleet within last 30d, no fleets in 30–180d prior
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
        corp_display_name=_corp_display_name,
    )


def latest_snapshot():
    return AllianceHealthSnapshot.objects.order_by("-computed_at").first()


def save_snapshot(payload: dict[str, Any] | None = None):
    data = payload if payload is not None else compute_alliance_health()
    computed_at = timezone.now()
    if "computed_at" in data:
        try:
            computed_at = datetime.fromisoformat(data["computed_at"])
            if timezone.is_naive(computed_at):
                computed_at = timezone.make_aware(computed_at)
        except (TypeError, ValueError):
            computed_at = timezone.now()
    return AllianceHealthSnapshot.objects.create(
        computed_at=computed_at, payload=data
    )
