"""Mentor metrics for learning managers.

Mentoring data is small (a few hundred requests a quarter), so this runs on
request. The impact comparison reads fleet attendance for the mentored pilots
and their join-month cohort only.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import timedelta

from django.utils import timezone

from eveonline.helpers.characters.identity import characters_by_user
from fleets.models import EveFleetInstanceMember
from groups.models import UserCommunityStatusHistory
from learning.mentors import service
from learning.mentors.views import availability, person
from learning.models import (
    MentorClass,
    MentorClassTeacher,
    MentorProfile,
    MentorRequest,
)
from timezones.brackets import BRACKETS_BY_CODE

ZONES = ("USTZ", "EUTZ", "AUTZ")
MIN_IMPACT_N = 10


def _zone_of(code: str) -> str:
    return code.rstrip("+")


def compute(period_days: int = 90) -> dict:
    now = timezone.now()
    since = now - timedelta(days=period_days)
    period = MentorRequest.objects.filter(created_at__gte=since)
    # A hand-off is one pilot asking once, so count chains by their start.
    firsts = period.filter(passed_from__isnull=True)
    requests = firsts.count()
    pilots = firsts.values("pilot").distinct().count()

    booked_ids = set(
        period.filter(
            status__in=(
                MentorRequest.STATUS_BOOKED,
                MentorRequest.STATUS_DONE,
                MentorRequest.STATUS_NO_SHOW,
                MentorRequest.STATUS_UNCONFIRMED,
            )
        ).values_list("pk", flat=True)
    )
    first_booked = firsts.filter(pk__in=booked_ids).count()
    chains_booked = 0
    for req in firsts.prefetch_related("passed_to"):
        node, ok = req, False
        seen = 0
        while node is not None and seen < 20:
            if node.pk in booked_ids:
                ok = True
                break
            node = node.passed_to.first()
            seen += 1
        chains_booked += ok

    waits = [
        max(0.0, (r.answered_at - r.created_at).total_seconds() / 3600)
        for r in period.filter(pk__in=booked_ids, answered_at__isnull=False)
    ]
    done = period.filter(status=MentorRequest.STATUS_DONE)

    mentors = list(
        MentorProfile.objects.filter(status=MentorProfile.STATUS_APPROVED)
    )
    idents = service.pilot_identity([m.user_id for m in mentors])
    answers = service.answer_hours([m.pk for m in mentors], period_days)
    mentor_rows = []
    for m in mentors:
        mine = period.filter(mentor=m)
        hours = answers.get(m.pk)
        mentor_rows.append(
            {
                "person": person(idents.get(m.user_id)),
                "availability": availability(service.mentor_availability(m)),
                "classes": mine.filter(
                    status=MentorRequest.STATUS_DONE
                ).count(),
                "pilots": mine.filter(status=MentorRequest.STATUS_DONE)
                .values("pilot")
                .distinct()
                .count(),
                "answer_hours": round(hours, 1) if hours is not None else None,
                "answer_text": service.answer_text(hours),
                "passed": mine.filter(
                    status=MentorRequest.STATUS_PASSED
                ).count(),
            }
        )
    mentor_rows.sort(key=lambda r: (-r["classes"], r["person"]["name"]))

    waiting = MentorRequest.objects.filter(status=MentorRequest.STATUS_ASKED)
    zones = []
    for zone in ZONES:
        covering = [
            m
            for m in mentors
            if any(
                _zone_of(c) == zone
                for c in (m.weekday_brackets or [])
                + (m.weekend_brackets or [])
                if c in BRACKETS_BY_CODE
            )
        ]
        zone_waiting = sum(
            1
            for r in waiting
            if any(
                _zone_of(c) == zone
                for c in (r.weekday_brackets or [])
                + (r.weekend_brackets or [])
            )
        )
        zones.append(
            {
                "code": zone,
                "mentors": [person(idents.get(m.user_id)) for m in covering],
                "waiting": zone_waiting,
            }
        )

    topics = []
    for mc in MentorClass.objects.filter(status=MentorClass.STATUS_PUBLISHED):
        topics.append(
            {
                "title": mc.title,
                "requests": firsts.filter(mentor_class=mc).count(),
                "mentors": MentorClassTeacher.objects.filter(
                    mentor_class=mc,
                    status=MentorClassTeacher.STATUS_ACCEPTED,
                    mentor__status=MentorProfile.STATUS_APPROVED,
                ).count(),
                "waiting": waiting.filter(mentor_class=mc).count(),
            }
        )
    topics.sort(key=lambda t: (-t["requests"], t["title"]))

    return {
        "period_days": period_days,
        "requests": requests,
        "pilots": pilots,
        "got_mentor_pct": (
            round(100 * chains_booked / requests) if requests else None
        ),
        "first_mentor_pct": (
            round(100 * first_booked / requests) if requests else None
        ),
        "median_hours_to_booked": (
            round(statistics.median(waits), 1) if waits else None
        ),
        "classes_done": done.count(),
        "mentors": mentor_rows,
        "zones": zones,
        "topics": topics,
        "impact": impact(now),
    }


def _join_months(user_ids) -> dict[int, tuple[int, int]]:

    months = {}
    for uid, changed in (
        UserCommunityStatusHistory.objects.filter(user_id__in=user_ids)
        .order_by("changed_at")
        .values_list("user_id", "changed_at")
    ):
        months.setdefault(uid, (changed.year, changed.month))
    return months


def impact(now=None) -> list[dict]:
    """Mentored pilots against same-join-month pilots who weren't."""

    now = now or timezone.now()
    firsts: dict[int, object] = {}
    for uid, starts in (
        MentorRequest.objects.filter(status=MentorRequest.STATUS_DONE)
        .order_by("starts_at")
        .values_list("pilot_id", "starts_at")
    ):
        firsts.setdefault(uid, starts)
    eligible = {
        uid: d
        for uid, d in firsts.items()
        if d and d + timedelta(days=30) <= now
    }
    if len(eligible) < MIN_IMPACT_N:
        return [
            {
                "name": "Any class",
                "n": len(eligible),
                "measures": [],
            }
        ]
    months = _join_months(eligible)
    wanted_months = set(months.values())
    cohort: dict[tuple[int, int], set[int]] = defaultdict(set)
    seen = set()
    for uid, changed in UserCommunityStatusHistory.objects.order_by(
        "changed_at"
    ).values_list("user_id", "changed_at"):
        if uid in seen:
            continue
        seen.add(uid)
        key = (changed.year, changed.month)
        if key in wanted_months and uid not in firsts:
            cohort[key].add(uid)
    everyone = set(eligible) | {u for users in cohort.values() for u in users}
    owned = characters_by_user(everyone)
    owner = {c: u for u, cs in owned.items() for c in cs}
    start = min(eligible.values())
    joins: dict[int, list] = defaultdict(list)
    for cid, joined in EveFleetInstanceMember.objects.filter(
        character_id__in=list(owner), join_time__gte=start
    ).values_list("character_id", "join_time"):
        joins[owner[cid]].append(joined)

    def fleets(uid, a, b):
        return sum(1 for j in joins.get(uid, []) if a <= j < b)

    mentored_30, similar_30, mentored_90, similar_90 = [], [], [], []
    for uid, d in eligible.items():
        mentored_30.append(fleets(uid, d, d + timedelta(days=30)))
        peers = cohort.get(months.get(uid), set())
        if peers:
            similar_30.append(
                statistics.mean(
                    fleets(p, d, d + timedelta(days=30)) for p in peers
                )
            )
        if d + timedelta(days=90) <= now:
            a, b = d + timedelta(days=60), d + timedelta(days=90)
            mentored_90.append(1.0 if fleets(uid, a, b) else 0.0)
            if peers:
                similar_90.append(
                    statistics.mean(
                        1.0 if fleets(p, a, b) else 0.0 for p in peers
                    )
                )
    measures = [
        {
            "label": "Fleets in the next 30 days",
            "mentored": round(statistics.mean(mentored_30), 1),
            "similar": (
                round(statistics.mean(similar_30), 1) if similar_30 else 0.0
            ),
            "percent": False,
        }
    ]
    if len(mentored_90) >= MIN_IMPACT_N:
        measures.append(
            {
                "label": "Still flying after 90 days",
                "mentored": round(100 * statistics.mean(mentored_90)),
                "similar": (
                    round(100 * statistics.mean(similar_90))
                    if similar_90
                    else 0.0
                ),
                "percent": True,
            }
        )
    return [{"name": "Any class", "n": len(eligible), "measures": measures}]
