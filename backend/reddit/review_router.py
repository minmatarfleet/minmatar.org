"""The Reddit approver's screens: the approvals queue and the rotation.

Everything here calls the same functions the Django admin actions call
(`reddit.approval`, `reddit.schedule`, `reddit.service`), so approving,
publishing and submitting behave exactly as they did there. Posting itself
is unchanged; these endpoints only add a way to trigger the existing steps.
"""

import logging
from datetime import date, datetime
from typing import Optional

from django.utils import timezone
from ninja import Router, Schema

from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers.feature_access import can_use_feature
from reddit import approval, schedule
from reddit.models import (
    RedditPost,
    RedditPostChangeRequest,
    RedditPostTemplate,
    RedditSchedule,
)
from reddit.scheduling import dm_ceo_later, link_reddit_post_to_discord
from reddit.service import RedditService

logger = logging.getLogger(__name__)

FEATURE = "reddit.approvals.manage"
FORBIDDEN = "You can't review Reddit posts."

review_router = Router(tags=["Reddit"])


class RedditReviewItem(Schema):
    template_id: int
    # Null when the template itself (no edit) is what waits for approval.
    change_id: Optional[int] = None
    corporation_id: int
    corporation_name: str
    corporation_ticker: str
    first_approval: bool
    current_title: str
    current_content: str
    requested_title: str
    requested_content: str
    submitted_by: Optional[str] = None
    submitted_at: Optional[datetime] = None


class RedditReviewQueue(Schema):
    items: list[RedditReviewItem]


class RedditRejectRequest(Schema):
    note: str = ""


class RedditReviewDecision(Schema):
    changed: bool
    notified: bool


class RedditRotationPost(Schema):
    post_id: int
    template_id: int
    corporation_id: Optional[int] = None
    corporation_name: str
    corporation_ticker: str
    title: str
    scheduled_for: datetime
    slot_date: date
    status: str
    reddit_url: str
    delivery_method: str
    has_discord_channel: bool
    # Whether its template has ever been posted to Reddit.
    can_link_to_discord: bool


class RedditRotationMonth(Schema):
    schedule_id: int
    month: date
    status: str
    published_at: Optional[datetime] = None
    posts: list[RedditRotationPost]


class RedditRotation(Schema):
    months: list[RedditRotationMonth]


class RedditActionResult(Schema):
    ok: bool
    detail: str = ""


def _denied(request):
    if can_use_feature(request.user, FEATURE):
        return None
    return 403, ErrorResponse(detail=FORBIDDEN)


def _item(template, change) -> dict:
    corporation = template.corporation
    return {
        "template_id": template.id,
        "change_id": change.id if change else None,
        "corporation_id": corporation.corporation_id,
        "corporation_name": corporation.name,
        "corporation_ticker": corporation.ticker or "",
        "first_approval": not template.approved,
        "current_title": template.title,
        "current_content": template.content,
        "requested_title": change.title if change else template.title,
        "requested_content": change.content if change else template.content,
        "submitted_by": (
            change.submitted_by.username
            if change and change.submitted_by
            else None
        ),
        "submitted_at": change.created_at if change else None,
    }


def decision_message(template, approved: bool, note: str = "") -> list[str]:
    corporation = template.corporation
    if approved:
        text = (
            f"Your Reddit post for {corporation.name} was approved: "
            f"**{template.title}**. It joins the rotation."
        )
    else:
        text = (
            f"Your Reddit post change for {corporation.name} was not "
            "approved. The words that were approved keep going out."
        )
        if note:
            text += f"\nReason: {note}"
    return [text]


def _notify(template, approved: bool, note: str = "") -> bool:
    # The CEO's existing DM path (queued for a worker, never inline).
    return dm_ceo_later(template, decision_message(template, approved, note))


@review_router.get(
    "/queue",
    response={200: RedditReviewQueue, 403: ErrorResponse},
    auth=AuthBearer(),
    summary="Reddit post templates and changes waiting for approval",
)
def get_queue(request):
    if (denied := _denied(request)) is not None:
        return denied
    items = []
    pending = (
        RedditPostChangeRequest.objects.filter(
            status=RedditPostChangeRequest.PENDING
        )
        .select_related("template__corporation", "submitted_by")
        .order_by("created_at")
    )
    seen = set()
    for change in pending:
        seen.add(change.template_id)
        items.append(_item(change.template, change))
    waiting = (
        RedditPostTemplate.objects.filter(approved=False)
        .exclude(pk__in=seen)
        .exclude(title="")
        .select_related("corporation")
        .order_by("updated_at")
    )
    items.extend(_item(template, None) for template in waiting)
    return {"items": items}


@review_router.post(
    "/changes/{change_id}/approve",
    response={
        200: RedditReviewDecision,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    auth=AuthBearer(),
    summary="Approve a requested change; it goes live in the rotation",
)
def approve_change(request, change_id: int):
    if (denied := _denied(request)) is not None:
        return denied
    change = (
        RedditPostChangeRequest.objects.select_related("template__corporation")
        .filter(pk=change_id)
        .first()
    )
    if change is None:
        return 404, ErrorResponse(detail="Change not found")
    changed = approval.approve(change, request.user)
    notified = False
    if changed:
        change.template.refresh_from_db()
        notified = _notify(change.template, True)
    return {"changed": changed, "notified": notified}


@review_router.post(
    "/changes/{change_id}/reject",
    response={
        200: RedditReviewDecision,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    auth=AuthBearer(),
    summary="Reject a requested change, with a reason for the CEO",
)
def reject_change(request, change_id: int, payload: RedditRejectRequest):
    if (denied := _denied(request)) is not None:
        return denied
    change = (
        RedditPostChangeRequest.objects.select_related("template__corporation")
        .filter(pk=change_id)
        .first()
    )
    if change is None:
        return 404, ErrorResponse(detail="Change not found")
    note = payload.note.strip()
    if not note:
        return 400, ErrorResponse(detail="Give the CEO a reason.")
    changed = approval.reject(change, request.user, note)
    notified = _notify(change.template, False, note) if changed else False
    return {"changed": changed, "notified": notified}


@review_router.post(
    "/templates/{template_id}/approve",
    response={
        200: RedditReviewDecision,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    auth=AuthBearer(),
    summary="Approve a template (or its waiting change)",
)
def approve_template(request, template_id: int):
    if (denied := _denied(request)) is not None:
        return denied
    template = (
        RedditPostTemplate.objects.select_related("corporation")
        .filter(pk=template_id)
        .first()
    )
    if template is None:
        return 404, ErrorResponse(detail="Post not found")
    changed = approval.approve_template(template, request.user)
    notified = False
    if changed:
        template.refresh_from_db()
        notified = _notify(template, True)
    return {"changed": changed, "notified": notified}


def _post_row(post: RedditPost) -> dict:
    template = post.template
    corporation = template.corporation
    posted = (
        template.posts.filter(status=RedditPost.POSTED)
        .exclude(reddit_url="")
        .exists()
    )
    return {
        "post_id": post.id,
        "template_id": template.id,
        "corporation_id": corporation.corporation_id,
        "corporation_name": corporation.name,
        "corporation_ticker": corporation.ticker or "",
        "title": post.title or template.title,
        "scheduled_for": post.scheduled_for,
        "slot_date": post.slot_date,
        "status": post.status,
        "reddit_url": post.reddit_url,
        "delivery_method": template.delivery_method,
        "has_discord_channel": bool(template.discord_channel_id),
        "can_link_to_discord": posted and bool(template.discord_channel_id),
    }


@review_router.get(
    "/rotation",
    response={200: RedditRotation, 403: ErrorResponse},
    auth=AuthBearer(),
    summary="This month's and next month's Reddit rotation",
)
def get_rotation(request):
    if (denied := _denied(request)) is not None:
        return denied
    # As the admin list does: opening it makes sure the drafts exist.
    schedule.refresh_drafts()
    months = []
    today = timezone.now().date().replace(day=1)
    for month in RedditSchedule.objects.filter(month__gte=today).order_by(
        "month"
    )[:3]:
        posts = month.slots.select_related("template__corporation").order_by(
            "scheduled_for"
        )
        months.append(
            {
                "schedule_id": month.id,
                "month": month.month,
                "status": month.status,
                "published_at": month.published_at,
                "posts": [_post_row(post) for post in posts],
            }
        )
    return {"months": months}


@review_router.post(
    "/schedules/{schedule_id}/publish",
    response={200: RedditActionResult, 403: ErrorResponse, 404: ErrorResponse},
    auth=AuthBearer(),
    summary="Publish a draft month: confirm its slots",
)
def publish_schedule(request, schedule_id: int):
    if (denied := _denied(request)) is not None:
        return denied
    month = RedditSchedule.objects.filter(pk=schedule_id).first()
    if month is None:
        return 404, ErrorResponse(detail="Month not found")
    if month.status != RedditSchedule.DRAFT:
        return {"ok": False, "detail": "Already published."}
    confirmed = schedule.publish(month, user=request.user)
    return {"ok": True, "detail": f"{confirmed} slot(s) confirmed."}


@review_router.post(
    "/schedules/{schedule_id}/regenerate",
    response={200: RedditActionResult, 403: ErrorResponse, 404: ErrorResponse},
    auth=AuthBearer(),
    summary="Work out a draft month again",
)
def regenerate_schedule(request, schedule_id: int):
    if (denied := _denied(request)) is not None:
        return denied
    month = RedditSchedule.objects.filter(pk=schedule_id).first()
    if month is None:
        return 404, ErrorResponse(detail="Month not found")
    if month.status != RedditSchedule.DRAFT:
        return {"ok": False, "detail": "Only a draft can be regenerated."}
    RedditSchedule.objects.filter(pk=month.pk).update(inputs_hash="")
    schedule.refresh_month(month.month, timezone.now())
    return {"ok": True, "detail": "Draft updated."}


@review_router.post(
    "/templates/{template_id}/submit",
    response={200: RedditActionResult, 403: ErrorResponse, 404: ErrorResponse},
    auth=AuthBearer(),
    summary="Submit a post to Reddit now (the admin's manual submit)",
)
def submit_template(request, template_id: int):
    if (denied := _denied(request)) is not None:
        return denied
    template = (
        RedditPostTemplate.objects.select_related("corporation")
        .filter(pk=template_id)
        .first()
    )
    if template is None:
        return 404, ErrorResponse(detail="Post not found")
    try:
        post = RedditService().post_recriutment_ad(template)
    except Exception as error:  # the admin shows the same failure
        logger.warning("Manual Reddit submit failed", exc_info=True)
        return {"ok": False, "detail": f"Failed to submit: {error}"}
    if post.status == RedditPost.POSTED:
        return {"ok": True, "detail": "Submitted to Reddit."}
    return {"ok": False, "detail": "Reddit rejected the post."}


@review_router.post(
    "/templates/{template_id}/link-discord",
    response={200: RedditActionResult, 403: ErrorResponse, 404: ErrorResponse},
    auth=AuthBearer(),
    summary="Link a template's last Reddit post to its Discord channel",
)
def link_discord(request, template_id: int):
    if (denied := _denied(request)) is not None:
        return denied
    template = (
        RedditPostTemplate.objects.select_related("corporation")
        .filter(pk=template_id)
        .first()
    )
    if template is None:
        return 404, ErrorResponse(detail="Post not found")
    if not template.discord_channel_id:
        return {"ok": False, "detail": "No Discord channel is set."}
    post = (
        template.posts.filter(status=RedditPost.POSTED)
        .exclude(reddit_url="")
        .first()
    )
    if post is None:
        return {
            "ok": False,
            "detail": "Never posted to Reddit. Submit a post first.",
        }
    done = link_reddit_post_to_discord(template, post.reddit_url, post.title)
    return {"ok": bool(done), "detail": "" if done else "Link failed."}
