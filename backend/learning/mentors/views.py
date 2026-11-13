"""Build the /api/learning/mentors responses (plain dicts)."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from groups.helpers.feature_access import can_use_feature
from learning.mentors import availability as avail
from learning.mentors import requirements as reqs
from learning.mentors import service
from learning.models import (
    MENTOR_CLASS_COVER_CHOICES,
    MentorClass,
    MentorClassTeacher,
    MentorProfile,
    MentorRequest,
)

FEATURE_REQUEST = "learning.mentors"
FEATURE_MANAGE = "learning.manage"
FIT_ORDER = {"evenings": 0, "weekdays": 1, "weekends": 2, "none": 3}


def can_request(user) -> bool:
    return can_use_feature(user, FEATURE_REQUEST)


def can_manage(user) -> bool:
    return can_use_feature(user, FEATURE_MANAGE)


def person(ident: dict | None) -> dict:
    ident = ident or {}
    return {
        "user_id": ident.get("user_id") or 0,
        "name": ident.get("name", ""),
        "character_id": ident.get("character_id"),
        "portrait": ident.get("portrait", ""),
        "corp": ident.get("corp", ""),
        "corporation_id": ident.get("corporation_id"),
        "discord_handle": ident.get("handle", ""),
        "discord_id": (
            str(ident["discord_id"]) if ident.get("discord_id") else None
        ),
    }


def availability(a: avail.Availability) -> dict:
    return {
        "weekday_brackets": list(a.weekday_brackets),
        "weekend_brackets": list(a.weekend_brackets),
        "days": list(a.days),
    }


def class_ref(mc: MentorClass) -> dict:
    return {
        "id": mc.pk,
        "slug": mc.slug,
        "title": mc.title,
        "minutes": mc.minutes,
        "where": mc.where,
        "status": mc.status,
    }


def mentor_cards(
    mentors: list[MentorProfile], viewer_availability, now=None
) -> list[dict]:
    if not mentors:
        return []
    ids = [m.pk for m in mentors]
    idents = service.pilot_identity([m.user_id for m in mentors])
    answers = service.answer_hours(ids)
    queues = service.queue_counts(ids)
    taught = service.classes_taught(ids)
    teaching: dict[int, list] = {}
    for row in (
        MentorClassTeacher.objects.filter(
            mentor_id__in=ids,
            status=MentorClassTeacher.STATUS_ACCEPTED,
            mentor_class__status=MentorClass.STATUS_PUBLISHED,
        )
        .select_related("mentor_class")
        .order_by("mentor_class__title")
    ):
        teaching.setdefault(row.mentor_id, []).append(
            class_ref(row.mentor_class)
        )
    cards = []
    for mentor in mentors:
        mine = service.mentor_availability(mentor)
        fit = (
            avail.fit(viewer_availability, mine, now)
            if viewer_availability
            else "none"
        )
        hours = answers.get(mentor.pk)
        cards.append(
            {
                "mentor_id": mentor.pk,
                "person": person(idents.get(mentor.user_id)),
                "availability": availability(mine),
                "fit": fit,
                "answer_hours": round(hours, 1) if hours is not None else None,
                "answer_text": service.answer_text(hours),
                "queue": queues.get(mentor.pk, 0),
                "classes_taught": taught.get(mentor.pk, 0),
                "full": service.is_full(mentor, now),
                "classes": teaching.get(mentor.pk, []),
            }
        )
    cards.sort(
        key=lambda c: (
            FIT_ORDER.get(c["fit"], 9),
            c["full"],
            -c["classes_taught"],
            c["person"]["name"].lower(),
        )
    )
    return cards


def request_rows(requests, viewer=None) -> list[dict]:
    requests = list(requests)
    if not requests:
        return []
    user_ids = set()
    for req in requests:
        user_ids.update({req.pilot_id, req.mentor.user_id})
        if req.passed_from_id:
            user_ids.add(req.passed_from.mentor.user_id)
    idents = service.pilot_identity(user_ids)
    answers = service.answer_hours({r.mentor_id for r in requests})
    now = timezone.now()
    rows = []
    for req in requests:
        role = None
        if viewer is not None:
            role = (
                "pilot"
                if viewer.pk == req.pilot_id
                else "mentor" if viewer.pk == req.mentor.user_id else None
            )
        answered = (
            req.pilot_answered_at
            if role == "pilot"
            else req.mentor_answered_at
        )
        can_feedback = bool(
            role
            and req.status == MentorRequest.STATUS_BOOKED
            and req.starts_at
            and req.starts_at <= now
            and not answered
        )
        rows.append(
            {
                "id": req.pk,
                "status": req.status,
                "mentor_class": class_ref(req.mentor_class),
                "pilot": person(idents.get(req.pilot_id)),
                "mentor": person(idents.get(req.mentor.user_id)),
                "mentor_id": req.mentor_id,
                "note": req.note,
                "starts_at": req.starts_at,
                "bring": req.bring,
                "created_at": req.created_at,
                "answered_at": req.answered_at,
                "availability": availability(
                    service.request_availability(req)
                ),
                "passed_from_name": (
                    idents.get(req.passed_from.mentor.user_id, {}).get(
                        "name", ""
                    )
                    if req.passed_from_id
                    else ""
                ),
                "answer_text": service.answer_text(answers.get(req.mentor_id)),
                "pilot_rating": req.pilot_rating,
                "mentor_outcome": req.mentor_outcome,
                "can_give_feedback": can_feedback,
            }
        )
    return rows


def _requests_qs():
    return MentorRequest.objects.select_related(
        "mentor", "mentor_class", "passed_from__mentor"
    )


def me(user) -> dict:
    profile = service.profile_for(user)
    open_asks = 0
    if profile and profile.approved:
        open_asks = MentorRequest.objects.filter(
            mentor=profile, status=MentorRequest.STATUS_ASKED
        ).count()
    return {
        "can_request": can_request(user),
        "is_mentor": bool(profile and profile.approved),
        "mentor_status": profile.status if profile else None,
        "can_manage": can_manage(user),
        "open_asks": open_asks,
    }


def home(user, now=None) -> dict:
    base = me(user)
    viewer = service.default_pilot_availability(user)
    mentors = list(
        MentorProfile.objects.filter(
            status=MentorProfile.STATUS_APPROVED,
            taking_requests=True,
            teaching__status=MentorClassTeacher.STATUS_ACCEPTED,
            teaching__mentor_class__status=MentorClass.STATUS_PUBLISHED,
        )
        .exclude(user=user)
        .distinct()
    )
    mine = _requests_qs().filter(pilot=user)
    open_rows = mine.filter(status__in=MentorRequest.OPEN_STATUSES).order_by(
        "starts_at", "created_at"
    )
    # A class waiting on feedback is still booked; closed ones count as past.
    past_count = mine.exclude(
        status__in=MentorRequest.OPEN_STATUSES + (MentorRequest.STATUS_PASSED,)
    ).count()
    return {
        **base,
        "availability": availability(viewer),
        "classes": request_rows(open_rows, user),
        "past_count": past_count,
        "mentors": mentor_cards(mentors, viewer, now),
    }


def past_classes(user) -> list[dict]:
    rows = (
        _requests_qs()
        .filter(pilot=user)
        .exclude(
            status__in=MentorRequest.OPEN_STATUSES
            + (MentorRequest.STATUS_PASSED,)
        )
        .order_by("-closed_at", "-created_at")[:50]
    )
    return request_rows(rows, user)


def class_detail(user, mentor_class: MentorClass) -> dict:
    checks = reqs.check(user, mentor_class.requirements)
    teachers = list(
        MentorProfile.objects.filter(
            status=MentorProfile.STATUS_APPROVED,
            teaching__mentor_class=mentor_class,
            teaching__status=MentorClassTeacher.STATUS_ACCEPTED,
        )
        .exclude(user=user)
        .distinct()
    )
    author = None
    if mentor_class.author_id:
        author = person(
            service.pilot_identity([mentor_class.author_id]).get(
                mentor_class.author_id
            )
        )
    open_req = service.open_request_for(user, mentor_class)
    return {
        "id": mentor_class.pk,
        "slug": mentor_class.slug,
        "title": mentor_class.title,
        "summary": mentor_class.summary,
        "outline": [
            line.strip()
            for line in mentor_class.outline.splitlines()
            if line.strip()
        ],
        "minutes": mentor_class.minutes,
        "where": mentor_class.where,
        "cover_image_url": mentor_class.cover_image_url,
        "status": mentor_class.status,
        "author": author,
        "requirements": [c.__dict__ for c in checks],
        "all_met": all(c.met for c in checks),
        "mentors": mentor_cards(
            teachers, service.default_pilot_availability(user)
        ),
        "pilots_taught": MentorRequest.objects.filter(
            mentor_class=mentor_class, status=MentorRequest.STATUS_DONE
        )
        .values("pilot")
        .distinct()
        .count(),
        "can_edit": can_edit_class(user, mentor_class),
        "open_request_id": open_req.pk if open_req else None,
    }


def can_edit_class(user, mentor_class: MentorClass) -> bool:
    """Classes are set up in Settings: only learning managers edit them."""
    return can_manage(user)


def mentoring(profile: MentorProfile) -> dict:
    now = timezone.now()
    reqs_qs = _requests_qs().filter(mentor=profile)
    asks = reqs_qs.filter(status=MentorRequest.STATUS_ASKED).order_by(
        "created_at"
    )
    booked = reqs_qs.filter(
        status=MentorRequest.STATUS_BOOKED, starts_at__gt=now
    ).order_by("starts_at")
    to_close = reqs_qs.filter(
        status=MentorRequest.STATUS_BOOKED,
        starts_at__lte=now,
        mentor_answered_at__isnull=True,
    ).order_by("starts_at")
    past = reqs_qs.filter(status=MentorRequest.STATUS_DONE).count()
    return {
        "record": service.mentor_record(profile),
        "asks": request_rows(asks, profile.user),
        "booked": request_rows(booked, profile.user),
        "to_close": request_rows(to_close, profile.user),
        "past_count": past,
    }


def profile_row(profile: MentorProfile | None) -> dict | None:
    if profile is None:
        return None
    return {
        "status": profile.status,
        "weekday_brackets": list(profile.weekday_brackets or []),
        "weekend_brackets": list(profile.weekend_brackets or []),
        "days": list(profile.days or []),
        "classes_per_week": profile.classes_per_week,
        "taking_requests": profile.taking_requests,
        "application_note": profile.application_note,
    }


def _teaching_row(row: MentorClassTeacher, counts, idents) -> dict:
    mc = row.mentor_class
    return {
        "mentor_class": class_ref(mc),
        "teacher_status": row.status,
        "is_author": mc.author_id == row.mentor.user_id,
        "author_name": idents.get(mc.author_id, {}).get("name", ""),
        "teacher_count": counts.get(mc.pk, 0),
    }


def settings(user) -> dict:
    profile = service.profile_for(user)
    teaching, invites, joinable = [], [], []
    if profile:
        rows = list(
            MentorClassTeacher.objects.filter(mentor=profile).select_related(
                "mentor_class", "mentor"
            )
        )
        class_ids = [r.mentor_class_id for r in rows]
        counts = dict(
            MentorClassTeacher.objects.filter(
                mentor_class_id__in=class_ids,
                status=MentorClassTeacher.STATUS_ACCEPTED,
            )
            .values_list("mentor_class_id")
            .annotate(n=Count("id"))
            .values_list("mentor_class_id", "n")
        )
        idents = service.pilot_identity(
            {r.mentor_class.author_id for r in rows}
        )
        for row in rows:
            target = (
                invites
                if row.status == MentorClassTeacher.STATUS_INVITED
                else teaching
            )
            target.append(_teaching_row(row, counts, idents))
        if profile.approved:
            joinable = [
                class_ref(mc)
                for mc in MentorClass.objects.filter(
                    status=MentorClass.STATUS_PUBLISHED
                ).exclude(pk__in=class_ids)
            ]
    return {
        "profile": profile_row(profile),
        "teaching": teaching,
        "invites": invites,
        "joinable": joinable,
    }


def class_edit(user, mentor_class: MentorClass) -> dict:
    teachers = list(
        MentorClassTeacher.objects.filter(
            mentor_class=mentor_class
        ).select_related("mentor")
    )
    idents = service.pilot_identity([t.mentor.user_id for t in teachers])
    return {
        "id": mentor_class.pk,
        "slug": mentor_class.slug,
        "title": mentor_class.title,
        "summary": mentor_class.summary,
        "outline": mentor_class.outline,
        "minutes": mentor_class.minutes,
        "where": mentor_class.where,
        "requirements": list(mentor_class.requirements or []),
        "cover_image_url": mentor_class.cover_image_url,
        "status": mentor_class.status,
        "review_note": mentor_class.review_note,
        "teachers": [
            {
                "mentor_id": t.mentor_id,
                "person": person(idents.get(t.mentor.user_id)),
                "status": t.status,
                "is_author": t.mentor.user_id == mentor_class.author_id,
            }
            for t in teachers
        ],
        "requirement_kinds": requirement_kinds(),
        "can_review": can_manage(user),
    }


def requirement_kinds() -> list[dict]:
    return [
        {"kind": kind, "label": label}
        for kind, label in reqs.KIND_LABELS.items()
    ]


def class_options() -> dict:
    """What the class editor offers: the cover gallery and requirement kinds."""
    return {
        "covers": [
            {"url": url, "label": label}
            for url, label in MENTOR_CLASS_COVER_CHOICES
        ],
        "requirement_kinds": requirement_kinds(),
    }


def _admin_classes(classes) -> list[dict]:
    classes = list(classes)
    since = timezone.now() - timedelta(days=90)
    counts = dict(
        MentorRequest.objects.filter(
            mentor_class__in=classes, created_at__gte=since
        )
        .exclude(status=MentorRequest.STATUS_PASSED)
        .values_list("mentor_class_id")
        .annotate(n=Count("id"))
        .values_list("mentor_class_id", "n")
    )
    teacher_rows = MentorClassTeacher.objects.filter(
        mentor_class__in=classes, status=MentorClassTeacher.STATUS_ACCEPTED
    ).select_related("mentor")
    teachers: dict[int, list[int]] = {}
    for row in teacher_rows:
        teachers.setdefault(row.mentor_class_id, []).append(row.mentor.user_id)
    idents = service.pilot_identity(
        {uid for ids in teachers.values() for uid in ids}
        | {mc.author_id for mc in classes}
    )
    return [
        {
            "id": mc.pk,
            "slug": mc.slug,
            "title": mc.title,
            "minutes": mc.minutes,
            "where": mc.where,
            "author_name": idents.get(mc.author_id, {}).get("name", ""),
            "teachers": [
                person(idents.get(uid)) for uid in teachers.get(mc.pk, [])
            ],
            "requests_90d": counts.get(mc.pk, 0),
            "requirement_count": len(mc.requirements or []),
            "cover_image_url": mc.cover_image_url,
            "status": mc.status,
            "review_note": mc.review_note,
        }
        for mc in classes
    ]


def _admin_mentors(profiles) -> list[dict]:
    profiles = list(profiles)
    idents = service.pilot_identity([p.user_id for p in profiles])
    counts = dict(
        MentorClassTeacher.objects.filter(
            mentor__in=profiles, status=MentorClassTeacher.STATUS_ACCEPTED
        )
        .values_list("mentor_id")
        .annotate(n=Count("id"))
        .values_list("mentor_id", "n")
    )
    return [
        {
            "mentor_id": p.pk,
            "person": person(idents.get(p.user_id)),
            "status": p.status,
            "availability": availability(service.mentor_availability(p)),
            "classes": counts.get(p.pk, 0),
            "taking_requests": p.taking_requests,
            "full": service.is_full(p),
            "application_note": p.application_note,
        }
        for p in profiles
    ]


def admin() -> dict:
    recent = (
        _requests_qs()
        .filter(
            status__in=(
                MentorRequest.STATUS_BOOKED,
                MentorRequest.STATUS_DONE,
                MentorRequest.STATUS_NO_SHOW,
                MentorRequest.STATUS_UNCONFIRMED,
            )
        )
        .exclude(
            pilot_answered_at__isnull=True, mentor_answered_at__isnull=True
        )
        .order_by("-starts_at")[:30]
    )
    recent = list(recent)
    idents = service.pilot_identity(
        {r.pilot_id for r in recent} | {r.mentor.user_id for r in recent}
    )
    ratings = dict(MentorRequest.RATING_CHOICES)
    outcomes = dict(MentorRequest.OUTCOME_CHOICES)
    reports = [
        {
            "id": r.pk,
            "pilot": person(idents.get(r.pilot_id)),
            "mentor": person(idents.get(r.mentor.user_id)),
            "class_title": r.mentor_class.title,
            "starts_at": r.starts_at,
            "pilot_rating": r.pilot_rating,
            "pilot_rating_label": ratings.get(r.pilot_rating, "No answer"),
            "pilot_note": r.pilot_note,
            "mentor_outcome": r.mentor_outcome,
            "mentor_outcome_label": outcomes.get(
                r.mentor_outcome, "No answer"
            ),
            "mentor_notes": r.mentor_notes,
        }
        for r in recent
    ]
    classes = MentorClass.objects.order_by("title")
    profiles = MentorProfile.objects.order_by("created_at")
    return {
        "reports": reports,
        "drafts": _admin_classes(
            classes.filter(status=MentorClass.STATUS_DRAFT)
        ),
        "review": _admin_classes(
            classes.filter(status=MentorClass.STATUS_REVIEW)
        ),
        "published": _admin_classes(
            classes.filter(status=MentorClass.STATUS_PUBLISHED)
        ),
        "hidden": _admin_classes(
            classes.filter(status=MentorClass.STATUS_HIDDEN)
        ),
        "applications": _admin_mentors(
            profiles.filter(status=MentorProfile.STATUS_APPLIED)
        ),
        "mentors": _admin_mentors(
            profiles.filter(status=MentorProfile.STATUS_APPROVED)
        ),
    }
