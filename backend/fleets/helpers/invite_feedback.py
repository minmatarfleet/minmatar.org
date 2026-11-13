"""One-round fleet invite feedback.

The form asks what the invites felt like. Who was invited, who opened the
fleet page, and who pressed Sitting out is already on the invite record, so
the form does not ask it. The cohort is frozen at send: later answers do
not change who was asked or what the form lists.

A private fleet's objective is never stored. See
docs/fleets/private-fleets.md.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone as dt_timezone

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models.functions import Coalesce
from django.utils import timezone

from app.links import site_url
from fleets.helpers.private_fleets import opted_out_user_ids
from fleets.models import (
    EveFleetInvite,
    FleetInviteFeedback,
    FleetInviteFeedbackRound,
)
from notifications.models import (
    NotificationChannel,
    NotificationDelivery,
    NotificationDeliveryStatus,
)
from notifications.service import notify_users

TYPE_KEY = "fleets.invite_feedback"
PROBE_KEY = "invite-feedback-probe"
WINDOW = timedelta(days=28)
REMIND_AFTER = timedelta(days=3)
COMMENT_MAX = 280
PAGE_PATH = "/fleets/invite-feedback/"
SOURCE_WEB = "web"
SOURCE_DISCORD = "discord"

LIST_HEADING = "Your invites, last few weeks."
WHY_HELP = "Leaving one open is common. These were still open."
COMMENT_HEADING = "One thing to change"
# The DM lists at most this many invites; the rest are "and N more".
DM_INVITE_LIMIT = 10
COMMENT_PLACEHOLDER = "Optional. A sentence is enough."

THANKS_HEADING = "Thanks. That's all we needed."
THANKS_BODY = (
    "Sitting out is only not this fleet. Stop fleet invites is what turns "
    "the DMs off."
)
THANKS_DETAIL = "You can change your answers until the survey closes."
NOT_INVITED_HEADING = "This isn't open for you."
NOT_INVITED_BODY = (
    "This survey is only for pilots who got a fleet invite in the last few "
    "weeks. If you did and this still shows, the DM is the link that opens "
    "your copy."
)
CLOSED_HEADING = "This survey is closed."
CLOSED_BODY = "Thanks if you already answered."

ERR_FELT = "Pick how these invites felt most of the time."
ERR_SITTING = "Pick which is closest for Sitting out."
ERR_WHY = "Pick what was most often going on."
ERR_WHY_TEXT = "Say what the other reason was."
ERR_WHY_LENGTH = "Keep the other reason to a sentence."
ERR_WHY_EXTRA = "You answered every invite, so that question doesn't apply."
ERR_IMPROVE = "Pick one or two that would have mattered."
ERR_NOTHING = '"Nothing. They were fine" stands on its own.'
ERR_COMMENT = "Keep the comment to a sentence."

FELT = (
    ("glad", "Glad I was asked"),
    ("fine", "Fine"),
    ("much", "A bit much"),
    ("stop", "I wanted them to stop"),
)
SITTING_OUT = (
    ("normal", 'A normal "not this time"'),
    ("letdown", "Like I'd be letting the FC down"),
    ("optout", "Like it might turn invites off"),
    ("unsure", "I wasn't sure what it did"),
    ("unnoticed", "I barely noticed it"),
)
WHY = (
    ("silence", "Saying nothing felt like no"),
    ("same", "Sitting out and Stop fleet invites felt like the same thing"),
    ("record", "I didn't want a no written down"),
    ("later", "I meant to decide later, then forgot"),
    (
        "ships",
        "I decide by picking a ship. No ship means I'm not coming.",
    ),
    ("mobile", "It was awkward on my phone"),
    ("other", "Other"),
)
IMPROVE = (
    ("fewer", "Fewer of them"),
    ("makeable", "Only fleets I can actually make"),
    ("lighter", 'A "not this time" that doesn\'t feel like a no'),
    ("why_picked", "Tell me why I was picked"),
    ("maybe", "A way to say maybe"),
    ("nothing", "Nothing. They were fine"),
)
NOTHING = "nothing"
ANSWER_LABELS = {
    EveFleetInvite.ANSWER_IN: "In",
    EveFleetInvite.ANSWER_OUT: "Sitting out",
    EveFleetInvite.ANSWER_PENDING: "No answer",
}
SOURCE_LABELS = {
    "first_week": "first week",
    "more_fleets": "under 3 fleets",
    "pilot": "by name",
    "tribe_group": "a group",
    "corporation": "a corporation",
}
_DROP_ORDER = ("not_started", "cancelled", "undelivered", "opted_out")


class InviteFeedbackError(Exception):
    def __init__(self, message: str, *, status_code: int = 400, errors=None):
        super().__init__(message)
        self.status_code = status_code
        self.errors = errors or [message]


def run_action(action: str, *, confirm: bool) -> str:
    if action == "preview":
        return preview_text()
    if action == "send":
        return send(confirm=confirm)
    if action == "remind":
        return remind(confirm=confirm)
    if action == "close":
        return close(confirm=confirm)
    raise InviteFeedbackError("Unknown action.")


def preview_text() -> str:
    survey = _current_round()
    if survey is None:
        kept, drops = live_cohort()
        report = _summarize_live(kept)
        report["dropped"] = drops
        report["frozen"] = False
    else:
        report = _summarize_rows(survey.responses.all())
        report["dropped"] = None
        report["frozen"] = True
        report["status"] = survey.status
    return _format_preview(report)


def send_one(username: str) -> str:
    """DM the form to one account. Does not open or change the real round."""
    name = (username or "").strip()
    if not name:
        return "Name the pilot. Nothing was sent."
    if _current_round() is not None:
        return (
            "The survey round already exists. Nothing was sent to " f"{name}."
        )
    user = User.objects.filter(username__iexact=name).first()
    if user is None:
        return f"No account named {name}. Nothing was sent."
    kept, unused_drops = live_cohort()
    items = kept.get(user.id, [])
    pending = any(
        item.answer == EveFleetInvite.ANSWER_PENDING for item in items
    )
    survey = FleetInviteFeedbackRound.objects.filter(key=PROBE_KEY).first()
    if survey is None:
        survey = FleetInviteFeedbackRound.objects.create(
            key=PROBE_KEY,
            since=timezone.now() - WINDOW,
            status=FleetInviteFeedbackRound.STATUS_OPEN,
        )
    row, created = FleetInviteFeedback.objects.get_or_create(
        round=survey,
        user=user,
        defaults={
            "cohort": (
                FleetInviteFeedback.COHORT_NO_ANSWER
                if pending
                else FleetInviteFeedback.COHORT_ANSWERED
            ),
            "invites": [snapshot_item(item) for item in items],
        },
    )
    if not created and row.sent_at is not None:
        return f"{user.username} already has this DM. Nothing else was sent."
    delivered, muted = _notify(survey, reminder=False, only_user_ids=[user.id])
    if delivered and items:
        return f"Sent the form to {user.username}."
    if delivered:
        return (
            f"Sent the form to {user.username}. They have no qualifying "
            "invite in the window."
        )
    if muted:
        return f"{user.username} has this DM turned off. Nothing was sent."
    return "Nothing was sent."


def send(*, confirm: bool) -> str:
    if not confirm:
        return (
            "Nothing was sent. Run this again with confirm to send the "
            "form. Preview it first."
        )
    existing = _current_round()
    if existing and existing.status == FleetInviteFeedbackRound.STATUS_CLOSED:
        return "This survey is closed. It is not sent again."
    if existing:
        return _retry_send(existing)
    kept, drops = live_cohort()
    if not kept:
        return (
            "Nobody would get the form. Nothing was sent.\n"
            + _dropped_line(drops)
        )
    now = timezone.now()
    key = f"invite-feedback-{now:%Y%m%d}"
    try:
        with transaction.atomic():
            survey = FleetInviteFeedbackRound.objects.create(
                key=key,
                since=now - WINDOW,
                status=FleetInviteFeedbackRound.STATUS_OPEN,
            )
            _freeze(survey, kept)
            delivered, muted = _notify(survey, reminder=False)
    except IntegrityError:
        return "Someone else just sent this. Run preview to see it."
    return _sent_line(delivered, muted)


def remind(*, confirm: bool) -> str:
    if not confirm:
        return (
            "Nothing was sent. Run this again with confirm to send the "
            "reminder."
        )
    survey = _current_round()
    if survey is None:
        return "Nothing has been sent yet."
    if survey.status == FleetInviteFeedbackRound.STATUS_CLOSED:
        return "This survey is closed."
    ready, skips = _reminder_candidates(survey)
    delivered, muted = _notify(
        survey, reminder=True, only_user_ids=[row.user_id for row in ready]
    )
    return _remind_line(delivered, muted, skips)


def close(*, confirm: bool) -> str:
    if not confirm:
        return "Nothing was closed. Run this again with confirm to close it."
    survey = _current_round()
    if survey is None:
        return "There is no survey to close."
    if survey.status == FleetInviteFeedbackRound.STATUS_CLOSED:
        return "This survey is already closed."
    survey.status = FleetInviteFeedbackRound.STATUS_CLOSED
    survey.closed_at = timezone.now()
    survey.save(update_fields=["status", "closed_at"])
    submitted = survey.responses.filter(submitted_at__isnull=False).count()
    cohort = survey.responses.count()
    return f"Closed. {submitted} of {cohort} answered."


def form_for(user, *, edit: bool) -> dict:
    row = (
        FleetInviteFeedback.objects.select_related("round")
        .filter(user=user)
        .order_by("-id")
        .first()
    )
    if row is None:
        return _panel("not_invited", NOT_INVITED_HEADING, NOT_INVITED_BODY)
    if row.round.status == FleetInviteFeedbackRound.STATUS_CLOSED:
        return _panel("closed", CLOSED_HEADING, CLOSED_BODY)
    if row.submitted_at and not edit:
        return _panel(
            "thanks", THANKS_HEADING, THANKS_BODY, detail=THANKS_DETAIL
        )
    return _form_panel(row)


def submit(user, payload: dict, *, source: str = SOURCE_WEB) -> dict:
    row = (
        FleetInviteFeedback.objects.select_related("round")
        .filter(user=user)
        .order_by("-id")
        .first()
    )
    if row is None:
        return _panel("not_invited", NOT_INVITED_HEADING, NOT_INVITED_BODY)
    if row.round.status == FleetInviteFeedbackRound.STATUS_CLOSED:
        return _panel("closed", CLOSED_HEADING, CLOSED_BODY)
    if source == SOURCE_DISCORD:
        payload = discord_payload(payload)
    errors = validate(row, payload, require_why_text=source != SOURCE_DISCORD)
    if errors:
        raise InviteFeedbackError(errors[0], errors=errors)
    pending = _has_pending(row)
    why = (payload.get("why") or "").strip()
    why_text = (payload.get("why_text") or "").strip()
    if not pending:
        why = ""
        why_text = ""
    elif why != "other":
        why_text = ""
    row.answers = {
        "felt": payload.get("felt") or "",
        "sitting_out": payload.get("sitting_out") or "",
        "why": why,
        "why_text": why_text,
        "improve": list(payload.get("improve") or []),
        "comment": (payload.get("comment") or "").strip(),
        "source": source,
    }
    row.submitted_at = timezone.now()
    row.save(update_fields=["answers", "submitted_at"])
    return _panel("thanks", THANKS_HEADING, THANKS_BODY, detail=THANKS_DETAIL)


def discord_payload(payload: dict) -> dict:
    """Fit a Discord form answer to the website's rules.

    The Discord form has five fields, so Other's reason is the comment, and
    its multi-select cannot make "Nothing" stand alone: a real pick beats it.
    """
    payload = dict(payload)
    improve = list(payload.get("improve") or [])
    if NOTHING in improve and len(improve) > 1:
        improve = [item for item in improve if item != NOTHING]
    payload["improve"] = improve
    why = (payload.get("why") or "").strip()
    if why == "other" and not (payload.get("why_text") or "").strip():
        payload["why_text"] = (payload.get("comment") or "").strip()
    return payload


def validate(
    row: FleetInviteFeedback, payload: dict, *, require_why_text: bool = True
) -> list[str]:
    errors = []
    felt = payload.get("felt") or ""
    sitting = payload.get("sitting_out") or ""
    why = (payload.get("why") or "").strip()
    why_text = (payload.get("why_text") or "").strip()
    improve = list(payload.get("improve") or [])
    comment = (payload.get("comment") or "").strip()
    if felt not in dict(FELT):
        errors.append(ERR_FELT)
    if sitting not in dict(SITTING_OUT):
        errors.append(ERR_SITTING)
    pending = _has_pending(row)
    if pending:
        if why not in dict(WHY):
            errors.append(ERR_WHY)
        elif why == "other" and not why_text and require_why_text:
            errors.append(ERR_WHY_TEXT)
        elif why == "other" and len(why_text) > COMMENT_MAX:
            errors.append(ERR_WHY_LENGTH)
    elif why or why_text:
        errors.append(ERR_WHY_EXTRA)
    known = dict(IMPROVE)
    if any(item not in known for item in improve):
        errors.append(ERR_IMPROVE)
    elif NOTHING in improve and len(improve) > 1:
        errors.append(ERR_NOTHING)
    elif not improve or len(improve) > 2:
        errors.append(ERR_IMPROVE)
    if len(comment) > COMMENT_MAX:
        errors.append(ERR_COMMENT)
    return errors


def live_cohort(now=None):
    """user id -> qualifying invites, newest fleet first, plus drop counts."""
    now = now or timezone.now()
    since = now - WINDOW
    invites = list(
        EveFleetInvite.objects.select_related("eve_fleet")
        .annotate(invited_at=Coalesce("sent_at", "created_at"))
        .filter(invited_at__gte=since)
    )
    opted = opted_out_user_ids({invite.user_id for invite in invites})
    drops: Counter = Counter()
    kept: dict[int, list] = defaultdict(list)
    for invite in invites:
        reason = _drop_reason(invite, now, opted)
        if reason:
            drops[reason] += 1
            continue
        kept[invite.user_id].append(invite)
    for items in kept.values():
        items.sort(key=lambda item: item.eve_fleet.start_time, reverse=True)
    return kept, drops


def snapshot_item(invite: EveFleetInvite) -> dict:
    fleet = invite.eve_fleet
    private = bool(fleet.invite_only)
    return {
        "fleet_id": fleet.id,
        "start": fleet.start_time.isoformat(),
        "title": "" if private else (fleet.objective or "").strip(),
        "private": private,
        "answer": invite.answer,
        "source_kind": invite.source_kind or "",
        "invite_only": private,
        "opened": invite.first_viewed_at is not None,
    }


def display_title(item: dict) -> str:
    if item.get("private"):
        return "Private fleet"
    return (item.get("title") or "").strip() or "Fleet"


def format_when(value: str) -> str:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_timezone.utc)
    eve = parsed.astimezone(dt_timezone.utc)
    return eve.strftime("%a %-d %b, %H:%M")


def _current_round():
    return (
        FleetInviteFeedbackRound.objects.exclude(key=PROBE_KEY)
        .order_by("-id")
        .first()
    )


def _drop_reason(invite, now, opted) -> str | None:
    if invite.eve_fleet.start_time >= now:
        return "not_started"
    if invite.eve_fleet.status == "cancelled":
        return "cancelled"
    if invite.dm_delivered is not True:
        return "undelivered"
    if invite.user_id in opted:
        return "opted_out"
    return None


def _freeze(survey, kept: dict[int, list]) -> None:
    FleetInviteFeedback.objects.bulk_create(
        [
            FleetInviteFeedback(
                round=survey,
                user_id=user_id,
                cohort=(
                    FleetInviteFeedback.COHORT_NO_ANSWER
                    if any(
                        item.answer == EveFleetInvite.ANSWER_PENDING
                        for item in items
                    )
                    else FleetInviteFeedback.COHORT_ANSWERED
                ),
                invites=[snapshot_item(item) for item in items],
            )
            for user_id, items in kept.items()
        ]
    )


def _retry_send(survey) -> str:
    delivered, muted = _notify(survey, reminder=False)
    if delivered == 0 and muted == 0:
        return (
            "Everyone who can get this DM already has it. "
            "No new pilots were added."
        )
    if delivered == 0:
        return (
            f"No new DM went out. {_muted(muted)} " "No new pilots were added."
        )
    extra = ""
    if muted:
        extra = f" {_muted(muted)}"
    return (
        f"Sent the form to {_people(delivered)} who didn't get it the first "
        f"time.{extra} No new pilots were added."
    )


def _notify(survey, *, reminder: bool, only_user_ids=None) -> tuple[int, int]:
    rows = survey.responses.select_related("user")
    if reminder:
        if not only_user_ids:
            return 0, 0
        rows = rows.filter(user_id__in=only_user_ids)
    else:
        rows = rows.filter(sent_at__isnull=True)
        if only_user_ids is not None:
            rows = rows.filter(user_id__in=only_user_ids)
    rows = list(rows)
    users = [row.user for row in rows]
    if not users:
        return 0, 0
    key = _idempotency_key(survey, reminder=reminder)
    deliveries = notify_users(
        users,
        TYPE_KEY,
        _dm_context(survey, reminder=reminder),
        idempotency_key=key,
        stagger_rate_limited_channels=True,
        user_contexts={
            row.user_id: {"invite_lines": dm_invite_lines(row)} for row in rows
        },
    )
    delivered_ids = {delivery.user_id for delivery in deliveries}
    existing = set(
        NotificationDelivery.objects.filter(
            idempotency_key__in=[f"{key}:u{user.id}" for user in users],
            channel=NotificationChannel.DISCORD,
        ).values_list("user_id", flat=True)
    )
    ids = delivered_ids | existing
    stamp = "reminded_at" if reminder else "sent_at"
    if ids:
        survey.responses.filter(
            user_id__in=ids, **{f"{stamp}__isnull": True}
        ).update(**{stamp: timezone.now()})
    return len(ids), len(users) - len(ids)


def _reminder_candidates(survey):
    now = timezone.now()
    cutoff = now - REMIND_AFTER
    rows = list(survey.responses.all())
    opted = opted_out_user_ids([row.user_id for row in rows])
    key = _idempotency_key(survey, reminder=False)
    statuses = dict(
        NotificationDelivery.objects.filter(
            idempotency_key__in=[f"{key}:u{row.user_id}" for row in rows],
            channel=NotificationChannel.DISCORD,
        ).values_list("user_id", "status")
    )
    ready = []
    skips: Counter = Counter()
    sent_states = {
        NotificationDeliveryStatus.SENT,
        NotificationDeliveryStatus.READ,
    }
    for row in rows:
        if row.submitted_at:
            skips["answered"] += 1
        elif row.reminded_at:
            skips["reminded"] += 1
        elif row.user_id in opted:
            skips["opted_out"] += 1
        elif row.sent_at is None or row.sent_at > cutoff:
            skips["recent"] += 1
        elif statuses.get(row.user_id) not in sent_states:
            skips["failed"] += 1
        else:
            ready.append(row)
    return ready, skips


def _idempotency_key(survey, *, reminder: bool) -> str:
    key = f"fleet-invite-feedback:{survey.id}"
    if reminder:
        key += ":remind"
    return key


def _dm_context(survey, *, reminder: bool) -> dict:
    if reminder:
        title = "Still got a minute?"
        body = "The fleet invite survey is still open. A few questions."
    else:
        title = "We need your feedback"
        body = (
            "Hey! You've been invited to a few fleets lately- could you "
            "take two minutes to share some feedback on the process?"
        )
    return {
        "title": title,
        "body": body,
        "url": site_url(PAGE_PATH),
        "round_id": survey.id,
        "list_heading": LIST_HEADING,
    }


def dm_invite_lines(row: FleetInviteFeedback) -> list[str]:
    """The pilot's own invites for the DM, newest first, one per line."""
    items = row.invites or []
    lines = [
        f"{format_when(item['start'])} · {display_title(item)} · "
        f"{ANSWER_LABELS.get(item.get('answer') or '', 'No answer')}"
        for item in items[:DM_INVITE_LIMIT]
    ]
    extra = len(items) - DM_INVITE_LIMIT
    if extra > 0:
        lines.append(f"and {extra} more")
    return lines


def _people(count: int) -> str:
    noun = "pilot" if count == 1 else "pilots"
    return f"{count} {noun}"


def _muted(count: int) -> str:
    verb = "has" if count == 1 else "have"
    return f"{_people(count)} still {verb} this DM turned off."


def _sent_line(delivered: int, muted: int) -> str:
    sent = _people(delivered)
    if muted:
        return (
            f"Sent to {sent}. {_people(muted)} "
            f"{'has' if muted == 1 else 'have'} this DM turned off, "
            "and the link still works for them. The survey is open."
        )
    return f"Sent to {sent}. The survey is open."


def _remind_line(delivered: int, muted: int, skips: Counter) -> str:
    parts = [f"Reminded {_people(delivered)}."]
    if muted:
        verb = "has" if muted == 1 else "have"
        parts.append(f"{_people(muted)} {verb} this DM turned off.")
    labels = (
        ("failed", "whose first DM didn't send"),
        ("opted_out", "who turned fleet invites off"),
        ("recent", "not due yet"),
        ("answered", "who already answered"),
        ("reminded", "already reminded"),
    )
    bits = [f"{skips[key]} {label}" for key, label in labels if skips[key]]
    if bits:
        parts.append("Left out: " + ", ".join(bits) + ".")
    return " ".join(parts)


def _summarize_live(kept) -> dict:
    records = []
    for items in kept.values():
        pending = any(
            item.answer == EveFleetInvite.ANSWER_PENDING for item in items
        )
        kinds = {item.source_kind or "" for item in items}
        private = any(item.eve_fleet.invite_only for item in items)
        standard = any(not item.eve_fleet.invite_only for item in items)
        opened = any(item.first_viewed_at for item in items)
        records.append((pending, kinds, private, standard, opened))
    return _summarize(records)


def _summarize_rows(rows) -> dict:
    records = []
    for row in rows:
        invites = row.invites or []
        pending = any(item.get("answer") == "pending" for item in invites)
        kinds = {item.get("source_kind") or "" for item in invites}
        private = any(item.get("private") for item in invites)
        standard = any(not item.get("private") for item in invites)
        opened = any(item.get("opened") for item in invites)
        records.append((pending, kinds, private, standard, opened))
    return _summarize(records)


def _summarize(records) -> dict:
    sources: Counter = Counter()
    pending = private = standard = opened = 0
    for is_pending, kinds, is_private, is_standard, has_opened in records:
        pending += int(is_pending)
        private += int(is_private)
        standard += int(is_standard)
        opened += int(has_opened)
        sources.update(kinds)
    total = len(records)
    return {
        "pilots": total,
        "no_answer": pending,
        "answered": total - pending,
        "sources": sources,
        "private": private,
        "standard": standard,
        "opened": opened,
        "never_opened": total - opened,
    }


def _format_preview(report: dict) -> str:
    if report.get("frozen"):
        state = report.get("status") or "open"
        lines = [
            f"The survey is {state}. This is the list already sent. "
            "Pilots invited after it opened are not added."
        ]
    else:
        lines = ["Nothing is sent. This is who would get the form."]
    lines.append(
        f"{_people(report['pilots'])}. {report['no_answer']} left an invite "
        f"open, {report['answered']} answered every one."
    )
    lines.append(
        f"{report['private']} have a private fleet invite. "
        f"{report['standard']} have a standard one."
    )
    lines.append(
        f"{report['opened']} opened a fleet page. "
        f"{report['never_opened']} never did."
    )
    source_bits = [
        f"{count} {SOURCE_LABELS.get(kind, kind or 'unspecified')}"
        for kind, count in sorted(report["sources"].items())
        if count
    ]
    if source_bits:
        lines.append("Invited as: " + ", ".join(source_bits) + ".")
    if report.get("dropped") is not None:
        lines.append(_dropped_line(report["dropped"]))
    return "\n".join(lines)


def _dropped_line(drops: Counter) -> str:
    parts = [f"{drops[key]} {key.replace('_', ' ')}" for key in _DROP_ORDER]
    return "Dropped invites: " + ", ".join(parts) + "."


def _has_pending(row: FleetInviteFeedback) -> bool:
    return any(
        item.get("answer") == EveFleetInvite.ANSWER_PENDING
        for item in (row.invites or [])
    )


def _choices(pairs) -> list[dict]:
    return [{"key": key, "label": label} for key, label in pairs]


def _invite_rows(items, *, pending_only: bool) -> list[dict]:
    rows = []
    for item in items:
        if (
            pending_only
            and item.get("answer") != EveFleetInvite.ANSWER_PENDING
        ):
            continue
        rows.append(
            {
                "fleet_id": item.get("fleet_id") or 0,
                "when": format_when(item["start"]),
                "title": display_title(item),
                "answer": item.get("answer") or "",
                "answer_label": ANSWER_LABELS.get(
                    item.get("answer") or "", "No answer"
                ),
            }
        )
    return rows


def _stored_answers(row: FleetInviteFeedback) -> dict:
    raw = row.answers or {}
    improve = raw.get("improve") or []
    return {
        "felt": raw.get("felt") or "",
        "sitting_out": raw.get("sitting_out") or "",
        "why": raw.get("why") or "",
        "why_text": raw.get("why_text") or "",
        "improve": list(improve),
        "comment": raw.get("comment") or "",
    }


def _questions(row: FleetInviteFeedback) -> list[dict]:
    questions = [
        {
            "key": "felt",
            "short": "These invites felt…",
            "prompt": "Most of the time, these invites felt…",
            "help": "",
            "kind": "single",
            "badge": "Required",
            "choices": _choices(FELT),
        },
        {
            "key": "sitting_out",
            "short": "Sitting out felt like…",
            "prompt": "Which of these is closest for Sitting out?",
            "help": "",
            "kind": "single",
            "badge": "Required",
            "choices": _choices(SITTING_OUT),
        },
    ]
    if _has_pending(row):
        questions.append(
            {
                "key": "why",
                "short": "Why the open ones stayed open",
                "prompt": "On the ones still open, what was most often going on?",
                "help": WHY_HELP,
                "kind": "single",
                "badge": "Required",
                "choices": _choices(WHY),
            }
        )
    questions.append(
        {
            "key": "improve",
            "short": "What would have mattered",
            "prompt": "Which of these would have mattered for the invites above?",
            "help": "",
            "kind": "multi",
            "badge": "Pick up to two",
            "exclusive": NOTHING,
            "max": 2,
            "choices": _choices(IMPROVE),
        }
    )
    return questions


def _form_panel(row: FleetInviteFeedback) -> dict:
    invites = row.invites or []
    panel = _panel("form", "", "")
    panel.update(
        {
            "list_heading": LIST_HEADING,
            "invites": _invite_rows(invites, pending_only=False),
            "pending_invites": _invite_rows(invites, pending_only=True),
            "questions": _questions(row),
            "answers": _stored_answers(row),
            "comment_heading": COMMENT_HEADING,
            "comment_placeholder": COMMENT_PLACEHOLDER,
        }
    )
    return panel


def _panel(state: str, heading: str, body: str, *, detail: str = "") -> dict:
    return {
        "state": state,
        "heading": heading,
        "body": body,
        "detail": detail,
        "intro": "",
        "list_heading": "",
        "invites": [],
        "pending_invites": [],
        "questions": [],
        "answers": {
            "felt": "",
            "sitting_out": "",
            "why": "",
            "why_text": "",
            "improve": [],
            "comment": "",
        },
        "comment_heading": "",
        "comment_placeholder": "",
        "errors": [],
    }
