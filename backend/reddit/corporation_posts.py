"""The Settings tab's view of a corporation's Reddit post template."""

from django.utils import timezone

from discord.models import DiscordUser
from eveonline.helpers.corporations.permissions import ceo_user, user_is_ceo
from reddit.markdown import check_reddit_markdown
from reddit import approval, schedule
from reddit.models import (
    RedditAccount,
    RedditPost,
    RedditPostChangeRequest,
    RedditPostTemplate,
)
from reddit.scheduling import automatic_blocker

# Reddit's own limits for self posts.
TITLE_MAX = 250
CONTENT_MAX = 40000

UNSCHEDULED = "unscheduled"
READY = "ready"

# Where the post stands in the rotation.
ACTIVE = "active"
PAUSED = "paused"
ADMIN_PAUSED = "admin_paused"
NOT_SET_UP = "not_set_up"


class PostSettingsError(ValueError):
    """Invalid CEO input. `code` names the problem for the frontend;
    `problems` lists the Markdown Reddit can't render."""

    def __init__(self, code: str, problems=None):
        super().__init__(code)
        self.code = code
        self.problems = problems or []


def markdown_problems(content: str) -> list[dict]:
    return [
        {
            "code": problem.code,
            "line": problem.line,
            "excerpt": problem.excerpt,
            "blocking": problem.blocking,
        }
        for problem in check_reddit_markdown(content)
    ]


def _latest(template: RedditPostTemplate, status: str) -> RedditPost | None:
    return (
        template.posts.filter(status=status, delivered_at__isnull=False)
        .order_by("-delivered_at")
        .first()
    )


def rotation_status(template: RedditPostTemplate | None) -> str:
    if template is None:
        return NOT_SET_UP
    if template.paused:
        return PAUSED
    if not template.subreddit:
        return ADMIN_PAUSED
    return ACTIVE


def post_settings(corporation, user) -> dict:
    template = RedditPostTemplate.objects.filter(
        corporation=corporation
    ).first()
    # Posts go out as the CEO and reminders DM the CEO, so a director sees
    # the CEO's accounts, not their own.
    ceo = ceo_user(corporation)
    account = RedditAccount.objects.filter(user=ceo).first() if ceo else None
    discord_linked = bool(
        ceo and DiscordUser.objects.filter(user=ceo).exists()
    )
    data = {
        "corporation_id": corporation.corporation_id,
        "exists": template is not None,
        "title": "",
        "content": "",
        "delivery_method": RedditPostTemplate.ALLIANCE,
        "subreddit": RedditPostTemplate._meta.get_field("subreddit").default,
        "paused": False,
        "priority": RedditPostTemplate.NORMAL,
        "rotation_status": NOT_SET_UP,
        "interval_days": None,
        "upcoming": [],
        "recent_changes": [],
        "approved": False,
        "approved_at": None,
        "change_pending": False,
        "change_submitted_at": None,
        "change_rejected_note": None,
        "automatic_status": UNSCHEDULED,
        "last_post_at": None,
        "last_reddit_post_url": None,
        "last_reminder_at": None,
        "reddit_account": (
            {
                "username": account.reddit_username,
                "token_invalid": account.token_invalid,
            }
            if account
            else None
        ),
        "discord_linked": discord_linked,
        # Linking acts on the viewer's own Reddit account, so only the CEO.
        "can_link_account": user_is_ceo(user, corporation),
        "markdown_problems": [],
    }
    if template is None:
        return data
    now = timezone.now()
    # The CEO keeps editing their waiting change, not the approved words.
    change = approval.pending_change(template)
    words = change or template
    # A rejection is news until the CEO edits again.
    latest = change or template.change_requests.first()
    rejected = (
        latest
        if latest and latest.status == RedditPostChangeRequest.REJECTED
        else None
    )
    last_post = _latest(template, RedditPost.POSTED)
    last_reminder = _latest(template, RedditPost.REMINDED)
    in_rotation = template.in_rotation
    data.update(
        {
            "title": words.title,
            "content": words.content,
            "delivery_method": template.delivery_method,
            "subreddit": template.subreddit,
            "paused": template.paused,
            "priority": template.priority,
            "rotation_status": rotation_status(template),
            "interval_days": schedule.typical_interval_days(template),
            "upcoming": (
                [
                    {
                        "scheduled_for": post.scheduled_for,
                        "confirmed": post.status == RedditPost.CONFIRMED,
                    }
                    for post in schedule.upcoming(template, now)
                ]
                if in_rotation
                else []
            ),
            "recent_changes": (
                schedule.recent_changes(template, now) if in_rotation else []
            ),
            "approved": template.approved,
            "approved_at": template.approved_at,
            "change_pending": bool(change and template.approved),
            "change_submitted_at": (
                change.created_at if change and template.approved else None
            ),
            "change_rejected_note": (
                rejected.review_note if rejected else None
            ),
            "automatic_status": (
                (automatic_blocker(template) or READY)
                if in_rotation
                else UNSCHEDULED
            ),
            "last_post_at": last_post.delivered_at if last_post else None,
            "last_reddit_post_url": (
                last_post.reddit_url or None if last_post else None
            ),
            "last_reminder_at": (
                last_reminder.delivered_at if last_reminder else None
            ),
            "markdown_problems": markdown_problems(words.content),
        }
    )
    return data


def save_post_settings(
    corporation,
    title: str,
    content: str,
    delivery_method: str,
    paused: bool | None = None,
    user=None,
) -> RedditPostTemplate:
    """Create or update the corporation's template. `paused` of None leaves
    it as it is. Once a superuser has approved the post, a new title or body
    waits for them as a change request and the approved words keep going
    out (see `reddit.approval`). The rotation's drafts are brought up to
    date straight away, so the CEO sees their new estimates."""
    # Line numbers in Markdown problems refer to the text as typed.
    typed_content = content or ""
    title = (title or "").strip()
    content = typed_content.strip()
    if not title:
        raise PostSettingsError("title_required")
    if len(title) > TITLE_MAX:
        raise PostSettingsError("title_too_long")
    if not content:
        raise PostSettingsError("content_required")
    if len(content) > CONTENT_MAX:
        raise PostSettingsError("content_too_long")
    if delivery_method not in dict(RedditPostTemplate.DELIVERY_CHOICES):
        raise PostSettingsError("invalid_delivery_method")
    problems = markdown_problems(typed_content)
    if any(problem["blocking"] for problem in problems):
        raise PostSettingsError("markdown_invalid", problems)

    template = RedditPostTemplate.objects.filter(
        corporation=corporation
    ).first()
    if template is None:
        template = RedditPostTemplate(corporation=corporation)
    template.delivery_method = delivery_method
    if paused is not None:
        template.paused = paused
    approval.save_edit(template, title, content, user)
    schedule.refresh_drafts()
    return template
