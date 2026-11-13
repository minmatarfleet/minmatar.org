"""Mentor classes: requests, hand-offs, booking, reminders and close-out.

Life of a request (MentorRequest.status):

asked -> booked -> done | no_show | unconfirmed
asked -> passed (the next mentor who fits gets a new request) | expired
asked/booked -> cancelled

The mentor's 48-hour answer closes a booked class; "We moved it" puts it
back to asked so the mentor picks a new time. See docs/learning/mentors.md.
"""

from __future__ import annotations

import logging
import statistics
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.text import slugify

from discord.models import DiscordUser
from discord.outbox import queue_dm
from eveonline.helpers.characters.identity import (
    characters_by_user,
    primary_characters_for_users,
)
from eveonline.models import EveCorporation
from fleets.models import EveFleetInstanceMember
from learning.helpers import mark_learning_complete
from learning.mentors import availability as avail
from learning.mentors import discord as mdiscord
from learning.mentors import requirements as reqs
from learning.models import (
    ContentKind,
    Learning,
    MentorClass,
    MentorClassTeacher,
    MentorProfile,
    MentorRequest,
)
from timezones.services import timezone_for

logger = logging.getLogger(__name__)

ANSWER_WINDOW = timedelta(days=2)
REMINDER_BEFORE = timedelta(hours=24)
FOLLOW_UP_AFTER = timedelta(hours=48)
UNCONFIRMED_AFTER = timedelta(days=7)
PORTRAIT_URL = "https://images.evetech.net/characters/{}/portrait?size=128"


class MentorError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


# ------------------------------------------------------------ identities
def pilot_identity(user_ids) -> dict[int, dict]:
    """User id -> {name, character_id, portrait, corp, discord_id, handle}."""
    ids = [uid for uid in set(user_ids) if uid]
    mains = primary_characters_for_users(ids)
    discord = {
        row["user_id"]: row
        for row in DiscordUser.objects.filter(user_id__in=ids).values(
            "user_id", "id", "discord_tag"
        )
    }

    corp_ids = {
        m.corporation_id for m in mains.values() if m and m.corporation_id
    }
    corps = dict(
        EveCorporation.objects.filter(corporation_id__in=corp_ids).values_list(
            "corporation_id", "ticker"
        )
    )
    out = {}

    usernames = dict(
        User.objects.filter(pk__in=ids).values_list("pk", "username")
    )
    for uid in ids:
        main = mains.get(uid)
        row = discord.get(uid)
        out[uid] = {
            "user_id": uid,
            "name": (main.character_name if main else "")
            or usernames.get(uid, ""),
            "character_id": int(main.character_id) if main else None,
            "portrait": (
                PORTRAIT_URL.format(int(main.character_id)) if main else ""
            ),
            "corporation_id": main.corporation_id if main else None,
            "corp": corps.get(main.corporation_id, "") if main else "",
            "discord_id": int(row["id"]) if row else None,
            "handle": mdiscord.handle(row["discord_tag"]) if row else "",
        }
    return out


def _dm(user_id: int, payload: dict, context: str) -> None:
    discord_id = (
        DiscordUser.objects.filter(user_id=user_id)
        .values_list("id", flat=True)
        .first()
    )
    if discord_id:
        queue_dm(discord_id, payload=payload, context=context)


# ---------------------------------------------------------- availability
def default_pilot_availability(user) -> avail.Availability:
    """The pilot's timezone brackets for both weekdays and weekends."""

    row = timezone_for(user.pk)
    brackets = list(row.brackets or []) if row else []
    return avail.Availability.build(brackets, brackets, avail.ALL_DAYS)


def mentor_availability(profile: MentorProfile) -> avail.Availability:
    return avail.Availability.build(
        profile.weekday_brackets, profile.weekend_brackets, profile.days
    )


def request_availability(req: MentorRequest) -> avail.Availability:
    return avail.Availability.build(
        req.weekday_brackets, req.weekend_brackets, req.days
    )


def seed_mentor_availability(profile: MentorProfile) -> None:
    """Start a new mentor from their timezone brackets, every evening."""

    row = timezone_for(profile.user_id)
    brackets = list(row.brackets or []) if row else []
    profile.weekday_brackets = brackets
    profile.weekend_brackets = brackets
    profile.days = list(avail.ALL_DAYS)


# --------------------------------------------------------------- stats
def week_start(now: datetime | None = None) -> datetime:
    now = now or timezone.now()
    start = now - timedelta(days=now.weekday())
    return start.replace(hour=0, minute=0, second=0, microsecond=0)


def booked_this_week(profile: MentorProfile, now=None) -> int:
    start = week_start(now)
    return MentorRequest.objects.filter(
        mentor=profile,
        status__in=(
            MentorRequest.STATUS_BOOKED,
            MentorRequest.STATUS_DONE,
        ),
        starts_at__gte=start,
        starts_at__lt=start + timedelta(days=7),
    ).count()


def is_full(profile: MentorProfile, now=None) -> bool:
    return booked_this_week(profile, now) >= max(1, profile.classes_per_week)


def answer_hours(profile_ids, since_days: int = 90) -> dict[int, float]:
    """Mentor id -> median hours from request to accept."""
    since = timezone.now() - timedelta(days=since_days)
    rows = MentorRequest.objects.filter(
        mentor_id__in=profile_ids,
        answered_at__isnull=False,
        created_at__gte=since,
    ).exclude(status=MentorRequest.STATUS_PASSED)
    waits: dict[int, list[float]] = {}
    for mentor_id, created, answered in rows.values_list(
        "mentor_id", "created_at", "answered_at"
    ):
        waits.setdefault(mentor_id, []).append(
            (answered - created).total_seconds() / 3600
        )
    return {k: statistics.median(v) for k, v in waits.items()}


def answer_text(hours: float | None, default: str = "New mentor") -> str:
    """How fast a mentor answers. ``default`` is shown before they have
    answered anyone: pilots see "Within a day", managers "New mentor"."""
    if hours is None:
        return default
    if hours < 1:
        return "Within an hour"
    if hours < 20:
        return f"In about {round(hours)} hours"
    if hours < 36:
        return "In about a day"
    return f"Within {max(2, round(hours / 24))} days"


def queue_counts(profile_ids) -> dict[int, int]:
    return dict(
        MentorRequest.objects.filter(
            mentor_id__in=profile_ids, status=MentorRequest.STATUS_ASKED
        )
        .values_list("mentor_id")
        .annotate(n=Count("id"))
        .values_list("mentor_id", "n")
    )


def classes_taught(profile_ids) -> dict[int, int]:
    return dict(
        MentorRequest.objects.filter(
            mentor_id__in=profile_ids, status=MentorRequest.STATUS_DONE
        )
        .values_list("mentor_id")
        .annotate(n=Count("id"))
        .values_list("mentor_id", "n")
    )


def pilots_mentored(profile_ids) -> dict[int, int]:
    """Distinct pilots each mentor has finished a class with."""
    return dict(
        MentorRequest.objects.filter(
            mentor_id__in=profile_ids, status=MentorRequest.STATUS_DONE
        )
        .values_list("mentor_id")
        .annotate(n=Count("pilot_id", distinct=True))
        .values_list("mentor_id", "n")
    )


# ------------------------------------------------------------- classes
def teaching_classes(profile: MentorProfile, accepted=True):
    qs = MentorClassTeacher.objects.filter(mentor=profile).select_related(
        "mentor_class"
    )
    if accepted:
        qs = qs.filter(status=MentorClassTeacher.STATUS_ACCEPTED)
    return qs


def teaches(profile: MentorProfile, mentor_class: MentorClass) -> bool:
    return MentorClassTeacher.objects.filter(
        mentor=profile,
        mentor_class=mentor_class,
        status=MentorClassTeacher.STATUS_ACCEPTED,
    ).exists()


def unique_slug(title: str, exclude_pk: int | None = None) -> str:
    base = slugify(title)[:90] or "class"
    slug, n = base, 2
    qs = MentorClass.objects.all()
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    while qs.filter(slug=slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


def sync_learning(mentor_class: MentorClass) -> None:
    """Keep the class's Learning row (what certificates point at) current."""
    published = mentor_class.status == MentorClass.STATUS_PUBLISHED
    url = f"/learning/mentors/classes/{mentor_class.slug}/"
    learning = mentor_class.learning
    if learning is None:
        if not published:
            return
        slug = f"mentor-{mentor_class.slug}"[:100]
        learning, _ = Learning.objects.get_or_create(
            slug=slug,
            defaults={"title": mentor_class.title, "url": url},
        )
        mentor_class.learning = learning
        mentor_class.save(update_fields=["learning", "updated_at"])
    learning.title = mentor_class.title
    learning.summary = mentor_class.summary
    learning.url = url
    learning.content_kind = ContentKind.MENTOR_CLASS
    learning.estimated_minutes = mentor_class.minutes
    learning.published = published
    learning.save()


def set_class_status(mentor_class: MentorClass, status: str, note=""):
    if status not in dict(MentorClass.STATUS_CHOICES):
        raise MentorError("Unknown status.")
    mentor_class.status = status
    if note:
        mentor_class.review_note = note
    mentor_class.save(update_fields=["status", "review_note", "updated_at"])
    sync_learning(mentor_class)


# ----------------------------------------------------------- requests
def open_request_for(pilot, mentor_class) -> MentorRequest | None:
    return MentorRequest.objects.filter(
        pilot=pilot,
        mentor_class=mentor_class,
        status__in=MentorRequest.OPEN_STATUSES,
    ).first()


def _mentor_fits_text(req: MentorRequest) -> str:
    shared = avail.suggested_slots(
        request_availability(req), mentor_availability(req.mentor), limit=2
    )
    if not shared:
        return "No shared evenings in the next two weeks"
    return ", ".join(f"{s:%a} {s:%H}:00 EVE" for s in shared)


def _plays_text(req: MentorRequest) -> str:
    weekday = ", ".join(req.weekday_brackets) or "—"
    weekend = ", ".join(req.weekend_brackets) or "—"
    if weekday == weekend:
        return f"{weekday} on weekdays and weekends"
    return f"Weekdays {weekday} · weekends {weekend}"


def notify_mentor_of_request(req: MentorRequest) -> None:
    ident = pilot_identity([req.pilot_id])[req.pilot_id]
    payload = mdiscord.request_payload(
        request_id=req.pk,
        pilot_name=ident["name"],
        pilot_portrait=ident["portrait"],
        pilot_handle=ident["handle"],
        pilot_corp=ident["corp"],
        class_title=req.mentor_class.title,
        plays=_plays_text(req),
        fits=_mentor_fits_text(req),
        note=req.note,
        passed_on=req.passed_from_id is not None,
    )
    _dm(req.mentor.user_id, payload, f"mentor request {req.pk}")


def create_request(
    pilot,
    mentor: MentorProfile,
    mentor_class: MentorClass,
    *,
    note: str = "",
    weekday_brackets=None,
    weekend_brackets=None,
    days=None,
) -> MentorRequest:
    if mentor.user_id == pilot.pk:
        raise MentorError("You can't book a class with yourself.")
    if mentor_class.status != MentorClass.STATUS_PUBLISHED:
        raise MentorError("That class isn't open.", 404)
    if not (mentor.approved and mentor.taking_requests):
        raise MentorError("That mentor isn't taking requests right now.")
    if not teaches(mentor, mentor_class):
        raise MentorError("That mentor doesn't teach this class.")
    if is_full(mentor):
        raise MentorError("That mentor is full this week. Try another.")
    if open_request_for(pilot, mentor_class):
        raise MentorError("You already have this class asked or booked.")
    missing = [
        c.label
        for c in reqs.check(pilot, mentor_class.requirements)
        if not c.met
    ]
    if missing:
        raise MentorError("You don't meet: " + "; ".join(missing) + ".")
    available = avail.Availability.build(
        weekday_brackets, weekend_brackets, days
    )
    if not (available.weekday_brackets or available.weekend_brackets):
        raise MentorError("Pick at least one timezone you play in.")
    if not available.days:
        raise MentorError("Pick at least one day you play.")
    with transaction.atomic():
        req = MentorRequest.objects.create(
            pilot=pilot,
            mentor=mentor,
            mentor_class=mentor_class,
            note=(note or "").strip()[:1000],
            weekday_brackets=list(available.weekday_brackets),
            weekend_brackets=list(available.weekend_brackets),
            days=list(available.days),
        )
        notify_mentor_of_request(req)
    return req


def _chain_mentor_ids(req: MentorRequest) -> set[int]:
    ids, node = set(), req
    while node is not None:
        ids.add(node.mentor_id)
        node = node.passed_from
    return ids


def next_mentor(req: MentorRequest) -> MentorProfile | None:
    """The best mentor for this class who hasn't been asked yet."""
    asked = _chain_mentor_ids(req)
    pilot = request_availability(req)
    candidates = []
    for teacher in MentorClassTeacher.objects.filter(
        mentor_class=req.mentor_class,
        status=MentorClassTeacher.STATUS_ACCEPTED,
        mentor__status=MentorProfile.STATUS_APPROVED,
        mentor__taking_requests=True,
    ).select_related("mentor"):
        mentor = teacher.mentor
        if mentor.pk in asked or mentor.user_id == req.pilot_id:
            continue
        if is_full(mentor):
            continue
        hours = len(avail.shared_hours(pilot, mentor_availability(mentor)))
        if hours:
            candidates.append((-hours, mentor.pk, mentor))
    candidates.sort(key=lambda row: (row[0], row[1]))
    return candidates[0][2] if candidates else None


def hand_off(req: MentorRequest) -> MentorRequest | None:
    """After a pass or two days unanswered: ask the next mentor who fits."""
    mentor = next_mentor(req)
    if mentor is None:
        req.status = MentorRequest.STATUS_EXPIRED
        req.closed_at = timezone.now()
        req.save(update_fields=["status", "closed_at", "updated_at"])
        _dm(
            req.pilot_id,
            mdiscord.text_payload(
                f"No mentor could take your **{req.mentor_class.title}** "
                "request this time. Pick another mentor or try again later.",
                "Find a mentor",
                mdiscord.FIND_PATH,
            ),
            f"mentor request {req.pk} expired",
        )
        return None
    req.status = MentorRequest.STATUS_PASSED
    req.closed_at = timezone.now()
    req.save(update_fields=["status", "closed_at", "updated_at"])
    new = MentorRequest.objects.create(
        pilot=req.pilot,
        mentor=mentor,
        mentor_class=req.mentor_class,
        note=req.note,
        weekday_brackets=req.weekday_brackets,
        weekend_brackets=req.weekend_brackets,
        days=req.days,
        passed_from=req,
    )
    notify_mentor_of_request(new)
    return new


def _require_mentor(req: MentorRequest, user) -> None:
    if req.mentor.user_id != user.pk:
        raise MentorError("This request isn't yours.", 403)


def _require_party(req: MentorRequest, user) -> str:
    if req.pilot_id == user.pk:
        return "pilot"
    if req.mentor.user_id == user.pk:
        return "mentor"
    raise MentorError("This class isn't yours.", 403)


def pass_request(req: MentorRequest, user) -> MentorRequest | None:
    _require_mentor(req, user)
    if req.status != MentorRequest.STATUS_ASKED:
        raise MentorError("This request isn't waiting for you.")
    with transaction.atomic():
        req.answered_at = timezone.now()
        req.save(update_fields=["answered_at", "updated_at"])
        return hand_off(req)


def slots(req: MentorRequest, now=None) -> list[datetime]:
    return avail.suggested_slots(
        request_availability(req), mentor_availability(req.mentor), now
    )


def accept(req: MentorRequest, user, starts_at: datetime, bring="") -> None:
    _require_mentor(req, user)
    if req.status != MentorRequest.STATUS_ASKED:
        raise MentorError("This request isn't waiting for a time.")
    if timezone.is_naive(starts_at):
        starts_at = starts_at.replace(tzinfo=dt_timezone.utc)
    now = timezone.now()
    if starts_at <= now + timedelta(hours=1):
        raise MentorError("Pick a time at least an hour from now.")
    if starts_at > now + timedelta(days=30):
        raise MentorError("Pick a time in the next 30 days.")
    with transaction.atomic():
        req.status = MentorRequest.STATUS_BOOKED
        req.starts_at = starts_at
        req.bring = (bring or "").strip()[:200]
        req.answered_at = req.answered_at or now
        req.reminded_at = None
        req.followed_up_at = None
        req.save()
        _send_booked(req)


def _send_booked(req: MentorRequest) -> None:
    ids = pilot_identity([req.pilot_id, req.mentor.user_id])
    pilot, mentor = ids[req.pilot_id], ids[req.mentor.user_id]
    for me, other, as_mentor in (
        (pilot, mentor, False),
        (mentor, pilot, True),
    ):
        _dm(
            me["user_id"],
            mdiscord.booked_payload(
                request_id=req.pk,
                other_name=other["name"],
                other_portrait=other["portrait"],
                other_handle=other["handle"],
                other_discord_id=other["discord_id"],
                class_title=req.mentor_class.title,
                starts_at=req.starts_at,
                bring=req.bring,
                as_mentor=as_mentor,
            ),
            f"mentor request {req.pk} booked",
        )


def cancel(req: MentorRequest, user) -> None:
    role = _require_party(req, user)
    if req.status not in MentorRequest.OPEN_STATUSES:
        raise MentorError("This class is already closed.")
    with transaction.atomic():
        was_booked = req.status == MentorRequest.STATUS_BOOKED
        req.status = MentorRequest.STATUS_CANCELLED
        req.cancelled_by = user
        req.closed_at = timezone.now()
        req.save(
            update_fields=["status", "cancelled_by", "closed_at", "updated_at"]
        )
        ids = pilot_identity([req.pilot_id, req.mentor.user_id])
        canceller = ids[user.pk]["name"]
        other_id = req.mentor.user_id if role == "pilot" else req.pilot_id
        if was_booked or role == "pilot":
            _dm(
                other_id,
                mdiscord.text_payload(
                    f"{canceller} cancelled **{req.mentor_class.title}**"
                    + (
                        f" (<t:{int(req.starts_at.timestamp())}:F>)."
                        if req.starts_at
                        else "."
                    )
                ),
                f"mentor request {req.pk} cancelled",
            )


def confirm(req: MentorRequest, user) -> None:
    role = _require_party(req, user)
    if req.status != MentorRequest.STATUS_BOOKED:
        raise MentorError("This class isn't booked.")
    field = "pilot_confirmed_at" if role == "pilot" else "mentor_confirmed_at"
    setattr(req, field, timezone.now())
    req.save(update_fields=[field, "updated_at"])


def feedback(req: MentorRequest, user, answer: str, note: str = "") -> str:
    """The 48-hour answer from either side. Returns the role that answered."""
    role = _require_party(req, user)
    now = timezone.now()
    note = (note or "").strip()[:2000]
    if req.starts_at is None or req.starts_at > now:
        raise MentorError("You can answer once the class time has passed.")
    if role == "pilot":
        if answer not in dict(MentorRequest.RATING_CHOICES):
            raise MentorError("Unknown answer.")
        req.pilot_rating = answer
        req.pilot_note = note
        req.pilot_answered_at = now
        req.save(
            update_fields=[
                "pilot_rating",
                "pilot_note",
                "pilot_answered_at",
                "updated_at",
            ]
        )
        return role
    if answer not in dict(MentorRequest.OUTCOME_CHOICES):
        raise MentorError("Unknown answer.")
    if req.status != MentorRequest.STATUS_BOOKED:
        raise MentorError("This class is already closed.")
    with transaction.atomic():
        req.mentor_outcome = answer
        req.mentor_notes = note
        req.mentor_answered_at = now
        if answer in (
            MentorRequest.OUTCOME_DONE,
            MentorRequest.OUTCOME_ANOTHER,
        ):
            req.status = MentorRequest.STATUS_DONE
            req.closed_at = now
            if req.mentor_class.learning_id:
                mark_learning_complete(req.pilot, req.mentor_class.learning)
        elif answer == MentorRequest.OUTCOME_NO_SHOW:
            req.status = MentorRequest.STATUS_NO_SHOW
            req.closed_at = now
        else:  # moved: the mentor picks a new time
            req.status = MentorRequest.STATUS_ASKED
            req.starts_at = None
            req.reminded_at = None
            req.followed_up_at = None
            req.pilot_confirmed_at = None
            req.mentor_confirmed_at = None
        req.save()
        if answer == MentorRequest.OUTCOME_MOVED:
            _dm(
                req.mentor.user_id,
                mdiscord.text_payload(
                    f"Pick the new time for **{req.mentor_class.title}**.",
                    "Pick a time",
                    mdiscord.MENTEES_PATH,
                ),
                f"mentor request {req.pk} moved",
            )
    return role


# ------------------------------------------------------------ schedules
def send_reminders(now: datetime | None = None) -> int:
    now = now or timezone.now()
    due = MentorRequest.objects.filter(
        status=MentorRequest.STATUS_BOOKED,
        reminded_at__isnull=True,
        starts_at__gt=now,
        starts_at__lte=now + REMINDER_BEFORE,
    ).select_related("mentor", "mentor_class")
    sent = 0
    for req in due:
        with transaction.atomic():
            locked = (
                MentorRequest.objects.select_for_update()
                .filter(pk=req.pk, reminded_at__isnull=True)
                .update(reminded_at=now)
            )
            if not locked:
                continue
            ids = pilot_identity([req.pilot_id, req.mentor.user_id])
            pilot, mentor = ids[req.pilot_id], ids[req.mentor.user_id]
            for me, other in ((pilot, mentor), (mentor, pilot)):
                _dm(
                    me["user_id"],
                    mdiscord.reminder_payload(
                        request_id=req.pk,
                        other_name=other["name"],
                        other_discord_id=other["discord_id"],
                        class_title=req.mentor_class.title,
                        starts_at=req.starts_at,
                        bring=req.bring,
                    ),
                    f"mentor request {req.pk} reminder",
                )
            sent += 1
    return sent


def send_follow_ups(now: datetime | None = None) -> int:
    now = now or timezone.now()
    due = MentorRequest.objects.filter(
        status=MentorRequest.STATUS_BOOKED,
        followed_up_at__isnull=True,
        starts_at__lte=now - FOLLOW_UP_AFTER,
    ).select_related("mentor", "mentor_class")
    sent = 0
    for req in due:
        with transaction.atomic():
            locked = (
                MentorRequest.objects.select_for_update()
                .filter(pk=req.pk, followed_up_at__isnull=True)
                .update(followed_up_at=now)
            )
            if not locked:
                continue
            ids = pilot_identity([req.pilot_id, req.mentor.user_id])
            _dm(
                req.pilot_id,
                mdiscord.pilot_feedback_payload(
                    request_id=req.pk,
                    mentor_name=ids[req.mentor.user_id]["name"],
                    class_title=req.mentor_class.title,
                ),
                f"mentor request {req.pk} pilot feedback",
            )
            _dm(
                req.mentor.user_id,
                mdiscord.mentor_followup_payload(
                    request_id=req.pk,
                    pilot_name=ids[req.pilot_id]["name"],
                    class_title=req.mentor_class.title,
                ),
                f"mentor request {req.pk} mentor close-out",
            )
            sent += 1
    return sent


def expire_unanswered(now: datetime | None = None) -> int:
    now = now or timezone.now()
    stale = MentorRequest.objects.filter(
        status=MentorRequest.STATUS_ASKED,
        starts_at__isnull=True,
        created_at__lte=now - ANSWER_WINDOW,
    ).select_related("mentor", "mentor_class", "pilot")
    moved = 0
    for req in stale:
        with transaction.atomic():
            if (
                not MentorRequest.objects.select_for_update()
                .filter(pk=req.pk, status=MentorRequest.STATUS_ASKED)
                .exists()
            ):
                continue
            hand_off(req)
            moved += 1
    return moved


def close_unconfirmed(now: datetime | None = None) -> int:
    now = now or timezone.now()
    return MentorRequest.objects.filter(
        status=MentorRequest.STATUS_BOOKED,
        followed_up_at__lte=now - UNCONFIRMED_AFTER,
        mentor_answered_at__isnull=True,
    ).update(
        status=MentorRequest.STATUS_UNCONFIRMED, closed_at=now, updated_at=now
    )


# --------------------------------------------------------------- profiles
def profile_for(user) -> MentorProfile | None:
    return MentorProfile.objects.filter(user=user).first()


def approved_profile(user) -> MentorProfile | None:
    profile = profile_for(user)
    return profile if profile and profile.approved else None


def still_flying(user_ids, days: int = 30) -> set[int]:
    """Users with a character in an alliance fleet in the last `days`."""

    owned = characters_by_user(user_ids)
    owner = {cid: uid for uid, cids in owned.items() for cid in cids}
    if not owner:
        return set()
    since = timezone.now() - timedelta(days=days)
    flown = EveFleetInstanceMember.objects.filter(
        join_time__gte=since, character_id__in=list(owner)
    ).values_list("character_id", flat=True)
    return {owner[cid] for cid in flown if cid in owner}


def mentor_record(profile: MentorProfile) -> dict:
    done = MentorRequest.objects.filter(
        mentor=profile, status=MentorRequest.STATUS_DONE
    )
    pilots = set(done.values_list("pilot_id", flat=True))
    return {
        "classes_taught": done.count(),
        "pilots_mentored": len(pilots),
        "still_flying": len(still_flying(pilots)) if pilots else 0,
    }


def open_requests_q() -> Q:
    return Q(status__in=MentorRequest.OPEN_STATUSES)
