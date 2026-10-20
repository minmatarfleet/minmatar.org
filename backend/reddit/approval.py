"""Approving what a corporation's Reddit post says.

A superuser approves a template's title and body. After that, the CEO's
edits wait in a `RedditPostChangeRequest` and the approved words keep going
out until a superuser approves or rejects the change, much like fitting
change requests. Reviewers get a Discord DM once an edit has settled, since
the CEO's Settings tab autosaves as they type.
"""

import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone

from discord.outbox import queue_dm
from reddit.models import RedditPostChangeRequest, RedditPostTemplate

logger = logging.getLogger(__name__)

# How long an edit must sit untouched before reviewers hear about it.
SETTLE = timedelta(minutes=10)


def normalize_text(text: str | None) -> str:
    """Browsers send textarea line breaks as CRLF and the Settings tab
    sends LF; store and compare one form so an unchanged body is never an
    edit."""
    return (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def same_words(template: RedditPostTemplate, title: str, content: str) -> bool:
    return template.title.strip() == title.strip() and normalize_text(
        template.content
    ) == normalize_text(content)


def pending_change(
    template: RedditPostTemplate,
) -> RedditPostChangeRequest | None:
    if not template.pk:
        return None
    return template.change_requests.filter(
        status=RedditPostChangeRequest.PENDING
    ).first()


def _holds_edits(template: RedditPostTemplate) -> bool:
    """Approved words that go out automatically are kept until a change is
    approved. A Discord reminder is posted by the CEO by hand, so their
    edits go live straight away."""
    return bool(
        template.pk
        and template.approved
        and template.delivery_method in RedditPostTemplate.AUTOMATIC_METHODS
    )


def _clear_approval(template: RedditPostTemplate):
    template.approved = False
    template.approved_by = None
    template.approved_at = None


def save_edit(
    template: RedditPostTemplate, title: str, content: str, user=None
) -> RedditPostChangeRequest | None:
    """Save the template with the CEO's title and body (its other fields
    already set). Returns the change request waiting for review, if any."""
    content = normalize_text(content)
    title = title.strip()
    if _holds_edits(template):
        template.save()
        if same_words(template, title, content):
            withdraw(template)
            return None
        return _propose(template, title, content, user)

    if template.pk and template.approved:
        if not same_words(template, title, content):
            # A reminder post's words changed, so the approval no longer
            # covers them.
            _clear_approval(template)
    template.title = title
    template.content = content
    template.save()
    if template.approved or (
        template.delivery_method not in RedditPostTemplate.AUTOMATIC_METHODS
    ):
        withdraw(template)
        return None
    # Not approved yet: the request puts it in front of a reviewer.
    return _propose(template, title, content, user)


def _propose(template, title, content, user) -> RedditPostChangeRequest:
    for _ in range(2):
        try:
            with transaction.atomic():
                change = (
                    RedditPostChangeRequest.objects.select_for_update()
                    .filter(
                        template=template,
                        status=RedditPostChangeRequest.PENDING,
                    )
                    .first()
                )
                if change is None:
                    return RedditPostChangeRequest.objects.create(
                        template=template,
                        title=title,
                        content=content,
                        submitted_by=user,
                    )
                # Only real edits touch updated_at, which decides when
                # reviewers hear about it.
                if (change.title, change.content) != (title, content):
                    change.title = title
                    change.content = content
                    change.submitted_by = user or change.submitted_by
                    change.save()
                return change
        except IntegrityError:
            # Another autosave created it first; update that one.
            continue
    raise RuntimeError(f"Could not record a change to template {template.pk}")


def withdraw(template: RedditPostTemplate) -> int:
    if not template.pk:
        return 0
    return template.change_requests.filter(
        status=RedditPostChangeRequest.PENDING
    ).update(
        status=RedditPostChangeRequest.WITHDRAWN, reviewed_at=timezone.now()
    )


def approve(change: RedditPostChangeRequest, user) -> bool:
    """Put the requested words on the template and approve them. False if
    the request was no longer pending."""
    with transaction.atomic():
        change = RedditPostChangeRequest.objects.select_for_update().get(
            pk=change.pk
        )
        if change.status != RedditPostChangeRequest.PENDING:
            return False
        now = timezone.now()
        template = change.template
        template.title = change.title
        template.content = change.content
        template.approved = True
        template.approved_by = user
        template.approved_at = now
        template.save()
        change.status = RedditPostChangeRequest.APPROVED
        change.reviewed_by = user
        change.reviewed_at = now
        change.save()
    return True


def reject(change: RedditPostChangeRequest, user, note: str = "") -> bool:
    """Close the request; the template keeps the words it had."""
    return bool(
        RedditPostChangeRequest.objects.filter(
            pk=change.pk, status=RedditPostChangeRequest.PENDING
        ).update(
            status=RedditPostChangeRequest.REJECTED,
            reviewed_by=user,
            reviewed_at=timezone.now(),
            review_note=note[:500],
        )
    )


def approve_template(template: RedditPostTemplate, user) -> bool:
    """The admin's Approve action: approve the waiting change if there is
    one, otherwise the template's own words. False if nothing changed."""
    change = pending_change(template)
    if change is not None:
        return approve(change, user)
    if template.approved:
        return False
    template.approved = True
    template.approved_by = user
    template.approved_at = timezone.now()
    template.save()
    return True


def approval_saved(template: RedditPostTemplate, user):
    """The admin ticked or cleared Approved on the template itself."""
    if template.approved:
        template.approved_by = user
        template.approved_at = timezone.now()
        change = pending_change(template)
        # The request for a first approval carries the template's own
        # words, and ticking the box approves those.
        if change is not None and same_words(
            template, change.title, change.content
        ):
            RedditPostChangeRequest.objects.filter(pk=change.pk).update(
                status=RedditPostChangeRequest.APPROVED,
                reviewed_by=user,
                reviewed_at=template.approved_at,
            )
    else:
        template.approved_by = None
        template.approved_at = None


def review_url(change: RedditPostChangeRequest) -> str:
    base = (settings.MINMATAR_ADMIN_BASE_URL or settings.SITE_URL).rstrip("/")
    return f"{base}/admin/reddit/redditpostchangerequest/{change.pk}/change/"


def review_message(
    change: RedditPostChangeRequest, updated: bool = False
) -> str:
    template = change.template
    corporation = template.corporation
    if updated:
        heading = "Reddit post change updated"
    elif template.approved:
        heading = "Reddit post change to review"
    else:
        heading = "New Reddit post to approve"
    lines = [
        f"**{heading}: {corporation.name} [{corporation.ticker}]**",
        f"Title: {change.title}",
    ]
    if template.approved and change.title != template.title:
        lines.append(f"Was: {template.title}")
    lines.append(f"Review it: <{review_url(change)}>")
    return "\n".join(lines)


def notify_reviewers(now: datetime | None = None) -> int:
    """DM reviewers about requests that have stopped changing, once, and
    again if the CEO edits them after that. Returns how many went out."""
    now = now or timezone.now()
    reviewers = settings.REDDIT_REVIEWER_DISCORD_IDS
    due = (
        RedditPostChangeRequest.objects.filter(
            status=RedditPostChangeRequest.PENDING,
            updated_at__lte=now - SETTLE,
        )
        .filter(
            Q(notified_at__isnull=True) | Q(notified_at__lt=F("updated_at"))
        )
        .select_related("template__corporation")
    )
    sent = 0
    for change in due:
        # update() leaves updated_at alone, so this doesn't re-arm itself.
        claimed = RedditPostChangeRequest.objects.filter(
            pk=change.pk, notified_at=change.notified_at
        ).update(notified_at=now)
        if not claimed:
            continue
        message = review_message(
            change, updated=change.notified_at is not None
        )
        for discord_id in reviewers:
            queue_dm(
                discord_id,
                message=message,
                context=f"Reddit post change {change.pk} review",
            )
        sent += 1
    return sent
