"""The alliance Reddit rotation, month by month.

Each month starts as a draft worked out by `reddit.rotation` and is
published on PUBLISH_DAY of the month before, which confirms its slots. A draft is only worked out again when something it
depends on changes (see `rotation.fingerprint`), and then repaired rather
than rebuilt, so its estimates hold still. A published month only changes
when an admin moves a slot or a corporation pauses: a paused corporation's
slot goes to whoever is owed most, or is skipped if it is too close.
"""

import logging
from collections import Counter
from datetime import date, datetime, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from reddit import rotation, scheduling
from reddit.models import (
    RedditPost,
    RedditPostTemplate,
    RedditSchedule,
    RedditScheduleChange,
)

logger = logging.getLogger(__name__)

# Next month is published on this day of the month before.
PUBLISH_DAY = 24
# Months before this are never published automatically; an admin can.
AUTO_PUBLISH_FROM = date(2026, 11, 1)
# Slots this close when published, or when their corporation pauses, are
# dropped rather than sprung on someone.
MIN_NOTICE = timedelta(hours=48)
HEADS_UP = timedelta(hours=24)
# Earlier months whose fair share carries into a new one.
CARRY_MONTHS = 3

# Slots that are planned or went out: they count for the cooldown.
LIVE_STATUSES = [
    RedditPost.DRAFT,
    RedditPost.CONFIRMED,
    RedditPost.PENDING,
    RedditPost.POSTED,
    RedditPost.REMINDED,
]
UPCOMING_STATUSES = [RedditPost.DRAFT, RedditPost.CONFIRMED]


def rotation_templates():
    """Templates the rotation gives slots to (see `in_rotation`)."""
    return (
        RedditPostTemplate.objects.filter(paused=False)
        .exclude(subreddit="")
        .exclude(title="")
        .exclude(content="")
        .select_related("corporation")
        .order_by("pk")
    )


def member(template: RedditPostTemplate) -> rotation.Member:
    return rotation.Member(
        id=template.pk,
        weight=rotation.WEIGHTS.get(template.priority, 1),
        window=template.posting_window,
    )


def _posted_at(post: RedditPost) -> datetime:
    return post.scheduled_for or post.delivered_at or post.created_at


def _history(before: datetime, schedule: RedditSchedule):
    """Each template's posts in the cooldown before `before`, from other
    months and from posts submitted by hand. A draft month that has already
    started will never be published by itself, so its slots don't count."""
    since = before - rotation.COOLDOWN - timedelta(days=1)
    posts = (
        RedditPost.objects.filter(status__in=LIVE_STATUSES)
        .exclude(schedule=schedule)
        .exclude(
            status=RedditPost.DRAFT,
            schedule__month__lte=rotation.month_start(before.date()),
        )
        .filter(
            Q(scheduled_for__gte=since, scheduled_for__lt=before)
            | Q(
                scheduled_for__isnull=True,
                created_at__gte=since,
                created_at__lt=before,
            )
        )
    )
    history: dict[int, list[datetime]] = {}
    for post in posts:
        history.setdefault(post.template_id, []).append(_posted_at(post))
    return history


def _earlier_months(month: date) -> list[tuple[dict[int, int], Counter]]:
    """Published months that carry into this one."""
    start = month
    for _ in range(CARRY_MONTHS):
        start = rotation.previous_month(start)
    months = []
    for schedule in RedditSchedule.objects.filter(
        month__gte=start, month__lt=month, status=RedditSchedule.PUBLISHED
    ).order_by("month"):
        weights = {int(i): w for i, w in schedule.weights.items()}
        got = Counter(schedule.slots.values_list("template_id", flat=True))
        months.append((weights, got))
    return months


def _days(month: date, now: datetime) -> list[date]:
    """The month's slot dates still ahead."""
    return [
        day
        for day in rotation.slot_dates(month)
        if rotation.slot_time(day) > now
    ]


def _names(ids) -> dict[int, str]:
    return {
        t.pk: t.corporation.name
        for t in RedditPostTemplate.objects.filter(
            pk__in=list(ids)
        ).select_related("corporation")
    }


def _what_changed(old: dict, new: dict) -> str:
    """For admins: how the rotation differs from the last draft."""
    old = {int(i): w for i, w in old.items()}
    names = _names(set(old) | set(new))
    parts = []
    for i in sorted(set(old) | set(new)):
        name = names.get(i, f"#{i}")
        if i not in old:
            parts.append(f"{name} joined")
        elif i not in new:
            parts.append(f"{name} left")
        elif old[i] != new[i]:
            level = "high" if new[i] > old[i] else "normal"
            parts.append(f"{name} set to {level} priority")
    return "; ".join(parts) or "Earlier months or the cooldown changed"


def refresh_month(month: date, now: datetime) -> RedditSchedule:
    """Bring a draft month up to date. Does nothing to a published month,
    or when nothing the draft depends on has changed."""
    with transaction.atomic():
        schedule, _ = RedditSchedule.objects.get_or_create(month=month)
        schedule = RedditSchedule.objects.select_for_update().get(
            pk=schedule.pk
        )
        if schedule.is_published:
            return schedule

        templates = list(rotation_templates())
        members = [member(t) for t in templates]
        days = _days(month, now)
        first = rotation.slot_time(days[0]) if days else now
        history = _history(first, schedule)
        carry = rotation.carry_from(
            _earlier_months(month), {m.id for m in members}
        )
        inputs_hash = rotation.fingerprint(
            month, days, members, carry, history
        )
        if inputs_hash == schedule.inputs_hash:
            return schedule

        existing = {
            post.slot_date: post for post in schedule.slots.select_for_update()
        }
        previous = {d: p.template_id for d, p in existing.items()}
        quota = rotation.quotas(members, len(days), carry)
        assigned = rotation.plan(days, members, quota, history, previous)
        windows = {t.pk: t.posting_window for t in templates}
        weights = {m.id: m.weight for m in members}
        detail = _what_changed(schedule.weights, weights) if existing else ""

        for day, post in existing.items():
            if day not in assigned:
                if day in days:
                    _record(schedule, day, post.template_id, None, detail)
                post.delete()
        for day, template_id in assigned.items():
            when = rotation.slot_time(day, windows[template_id])
            post = existing.get(day)
            if post is None:
                if existing:
                    _record(schedule, day, None, template_id, detail)
                RedditPost.objects.create(
                    template_id=template_id,
                    schedule=schedule,
                    slot_date=day,
                    scheduled_for=when,
                    status=RedditPost.DRAFT,
                    created_at=now,
                )
            elif (post.template_id, post.scheduled_for) != (
                template_id,
                when,
            ):
                if post.template_id != template_id:
                    _record(
                        schedule, day, post.template_id, template_id, detail
                    )
                post.template_id = template_id
                post.scheduled_for = when
                post.save(update_fields=["template", "scheduled_for"])

        schedule.weights = {str(i): w for i, w in weights.items()}
        schedule.quotas = {str(i): q for i, q in quota.items()}
        schedule.inputs_hash = inputs_hash
        schedule.generated_at = now
        schedule.save()
    return schedule


def _record(schedule, day, from_id, to_id, detail, reason=None):
    RedditScheduleChange.objects.create(
        schedule=schedule,
        slot_date=day,
        from_template_id=from_id,
        to_template_id=to_id,
        reason=reason or RedditScheduleChange.ROTATION,
        detail=detail[:300],
    )


def refresh_drafts(now: datetime | None = None) -> list[RedditSchedule]:
    """This month (until it is published) and next month, in order, since
    next month's cooldown and fair share depend on this one."""
    now = now or timezone.now()
    this_month = rotation.month_start(now.date())
    return [
        refresh_month(month, now)
        for month in (this_month, rotation.next_month(this_month))
    ]


def publish(
    schedule: RedditSchedule, now: datetime | None = None, user=None
) -> int:
    """Confirm a draft month's slots. Slots closer than MIN_NOTICE are
    dropped. Returns the number confirmed."""
    now = now or timezone.now()
    schedule = refresh_month(schedule.month, now)
    with transaction.atomic():
        schedule = RedditSchedule.objects.select_for_update().get(
            pk=schedule.pk
        )
        if schedule.is_published:
            return 0
        drafts = schedule.slots.filter(status=RedditPost.DRAFT)
        drafts.filter(scheduled_for__lt=now + MIN_NOTICE).delete()
        confirmed = drafts.update(status=RedditPost.CONFIRMED)
        schedule.status = RedditSchedule.PUBLISHED
        schedule.published_at = now
        schedule.published_by = user
        schedule.save()
    logger.info("Published Reddit rotation %s: %s slots", schedule, confirmed)
    return confirmed


def publish_due(now: datetime | None = None) -> list[RedditSchedule]:
    """Publish next month once PUBLISH_DAY comes, and any month that has
    started without being published (the workers were down)."""
    now = now or timezone.now()
    this_month = rotation.month_start(now.date())
    due = [this_month]
    if now.day >= PUBLISH_DAY:
        due.append(rotation.next_month(this_month))
    published = []
    for schedule in RedditSchedule.objects.filter(
        month__in=due,
        month__gte=AUTO_PUBLISH_FROM,
        status=RedditSchedule.DRAFT,
    ):
        publish(schedule, now)
        published.append(schedule)
    return published


def reconcile_published(now: datetime | None = None) -> int:
    """Give away the confirmed slots of corporations that left the
    rotation. Returns how many slots changed."""
    now = now or timezone.now()
    changed = 0
    orphans = (
        RedditPost.objects.filter(
            status=RedditPost.CONFIRMED, scheduled_for__gt=now
        )
        .filter(
            Q(template__paused=True)
            | Q(template__subreddit="")
            | Q(template__title="")
            | Q(template__content="")
        )
        .select_related("schedule", "template__corporation")
        .order_by("scheduled_for")
    )
    for post in orphans:
        _release(post, now)
        changed += 1
    return changed


def _release(post: RedditPost, now: datetime):
    old = post.template
    new = None
    if post.scheduled_for - now >= MIN_NOTICE:
        new = _replacement(post)
    detail = f"{old.corporation.name} left the rotation"
    if new is None:
        post.status = RedditPost.SKIPPED
        post.fallback_reason = "paused"
        post.save(update_fields=["status", "fallback_reason"])
        _record(
            post.schedule,
            post.slot_date,
            old.pk,
            None,
            detail,
            RedditScheduleChange.PAUSED,
        )
        return
    post.template = new
    post.scheduled_for = rotation.slot_time(post.slot_date, new.posting_window)
    post.heads_up_sent_at = None
    post.save(update_fields=["template", "scheduled_for", "heads_up_sent_at"])
    _record(
        post.schedule,
        post.slot_date,
        old.pk,
        new.pk,
        detail,
        RedditScheduleChange.PAUSED,
    )
    scheduling.dm_ceo(
        new, [scheduling.extra_slot_message(new, post.scheduled_for)]
    )


def _replacement(post: RedditPost) -> RedditPostTemplate | None:
    """Whoever in the rotation is furthest below their quota for the month
    and clear of the cooldown."""
    schedule = post.schedule
    quota = {int(i): q for i, q in schedule.quotas.items()}
    used = Counter(
        schedule.slots.exclude(pk=post.pk).values_list(
            "template_id", flat=True
        )
    )
    best, best_key = None, None
    for template in rotation_templates():
        at = rotation.slot_time(post.slot_date, template.posting_window)
        nearby = (
            RedditPost.objects.filter(
                template=template, status__in=LIVE_STATUSES
            )
            .exclude(pk=post.pk)
            .filter(
                scheduled_for__gt=at - rotation.COOLDOWN,
                scheduled_for__lt=at + rotation.COOLDOWN,
            )
        )
        if nearby.exists():
            continue
        key = (quota.get(template.pk, 0) - used[template.pk], -template.pk)
        if best_key is None or key > best_key:
            best, best_key = template, key
    return best


def move_slot(
    post: RedditPost,
    template: RedditPostTemplate,
    scheduled_for: datetime,
    old_template: RedditPostTemplate,
    old_scheduled_for: datetime,
):
    """An admin moved a confirmed slot: log it and tell whoever it affects."""
    post.heads_up_sent_at = None
    post.save(update_fields=["heads_up_sent_at"])
    if post.schedule_id:
        _record(
            post.schedule,
            post.slot_date,
            old_template.pk,
            template.pk,
            "",
            RedditScheduleChange.ADMIN,
        )
    if old_template.pk != template.pk:
        scheduling.dm_ceo(
            old_template,
            [scheduling.slot_removed_message(old_template, old_scheduled_for)],
        )
        scheduling.dm_ceo(
            template, [scheduling.extra_slot_message(template, scheduled_for)]
        )
    elif old_scheduled_for != scheduled_for:
        scheduling.dm_ceo(
            template,
            [
                scheduling.slot_moved_message(
                    template, old_scheduled_for, scheduled_for
                )
            ],
        )


def send_heads_ups(now: datetime | None = None) -> int:
    """DM each CEO the day before their slot."""
    now = now or timezone.now()
    sent = 0
    posts = RedditPost.objects.filter(
        status=RedditPost.CONFIRMED,
        heads_up_sent_at__isnull=True,
        scheduled_for__lte=now + HEADS_UP,
        scheduled_for__gt=now + timedelta(hours=1),
    ).select_related("template__corporation")
    for post in posts:
        claimed = RedditPost.objects.filter(
            pk=post.pk, heads_up_sent_at__isnull=True
        ).update(heads_up_sent_at=now)
        if not claimed:
            continue
        scheduling.dm_ceo(
            post.template,
            [scheduling.heads_up_message(post.template, post.scheduled_for)],
        )
        sent += 1
    return sent


def deliver_due(now: datetime | None = None) -> list[str]:
    """Deliver every confirmed slot whose time has come, once each."""
    now = now or timezone.now()
    outcomes = []
    due = RedditPost.objects.filter(
        status=RedditPost.CONFIRMED, scheduled_for__lte=now
    ).select_related("template__corporation")
    for post in due:
        missed = now - post.scheduled_for > scheduling.CATCH_UP_WINDOW
        if not post.template.in_rotation or missed:
            RedditPost.objects.filter(
                pk=post.pk, status=RedditPost.CONFIRMED
            ).update(
                status=RedditPost.SKIPPED,
                fallback_reason="missed" if missed else "paused",
            )
            continue
        if not scheduling.claim(post):
            continue
        post.status = RedditPost.PENDING
        outcome = scheduling.deliver(post.template, post, now)
        logger.info("Reddit rotation slot %s: %s", post.slot_date, outcome)
        outcomes.append(outcome)
    return outcomes


def run(now: datetime | None = None) -> list[str]:
    """Everything the rotation does on each scheduler run."""
    now = now or timezone.now()
    refresh_drafts(now)
    publish_due(now)
    reconcile_published(now)
    send_heads_ups(now)
    return deliver_due(now)


def upcoming(template: RedditPostTemplate, now: datetime, limit: int = 4):
    """The template's next slots: confirmed ones, then draft estimates."""
    return list(
        template.posts.filter(
            status__in=UPCOMING_STATUSES, scheduled_for__gt=now
        ).order_by("scheduled_for")[:limit]
    )


def recent_changes(
    template: RedditPostTemplate, now: datetime, days: int = 14
) -> list[dict]:
    """Slots this template gained or lost lately, for the CEO."""
    changes = RedditScheduleChange.objects.filter(
        Q(from_template=template) | Q(to_template=template),
        created_at__gte=now - timedelta(days=days),
        slot_date__gte=now.date(),
    ).order_by("-created_at", "slot_date")[:6]
    return [
        {
            "created_at": change.created_at,
            "slot_date": change.slot_date,
            # The slot as this post would have it: late slots go out after
            # midnight, on the next day.
            "scheduled_for": rotation.slot_time(
                change.slot_date, template.posting_window
            ),
            "gained": change.to_template_id == template.pk,
            "reason": change.reason,
        }
        for change in changes
        if change.from_template_id != change.to_template_id
    ]


def typical_interval_days(template: RedditPostTemplate) -> int | None:
    if not template.in_rotation:
        return None
    total = sum(member(t).weight for t in rotation_templates())
    return rotation.typical_interval_days(member(template).weight, total)
