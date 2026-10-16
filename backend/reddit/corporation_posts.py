"""The CEO's view of their corporation's Reddit post template."""

from django.utils import timezone

from discord.models import DiscordUser
from reddit.markdown import check_reddit_markdown
from reddit.models import RedditAccount, RedditPost, RedditPostTemplate
from reddit.scheduling import DAY_NAMES, automatic_blocker, next_slot

# Reddit's own limits for self posts.
TITLE_MAX = 250
CONTENT_MAX = 40000

UNSCHEDULED = "unscheduled"
READY = "ready"


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
    return template.posts.filter(status=status).first()


def post_settings(corporation, user) -> dict:
    template = RedditPostTemplate.objects.filter(
        corporation=corporation
    ).first()
    account = RedditAccount.objects.filter(user=user).first()
    discord_linked = DiscordUser.objects.filter(user=user).exists()
    data = {
        "corporation_id": corporation.corporation_id,
        "exists": template is not None,
        "title": "",
        "content": "",
        "delivery_method": RedditPostTemplate.DISCORD_REMINDER,
        "subreddit": RedditPostTemplate._meta.get_field("subreddit").default,
        "posting_day": "",
        "posting_time": RedditPostTemplate._meta.get_field(
            "posting_time"
        ).default.strftime("%H:%M"),
        "next_run_at": None,
        "approved": False,
        "approved_at": None,
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
        "markdown_problems": [],
    }
    if template is None:
        return data
    last_post = _latest(template, RedditPost.POSTED)
    last_reminder = _latest(template, RedditPost.REMINDED)
    data.update(
        {
            "title": template.title,
            "content": template.content,
            "delivery_method": template.delivery_method,
            "subreddit": template.subreddit,
            "posting_day": template.posting_day,
            "posting_time": template.posting_time.strftime("%H:%M"),
            "next_run_at": next_slot(template, timezone.now()),
            "approved": template.approved,
            "approved_at": template.approved_at,
            "automatic_status": (
                (automatic_blocker(template) or READY)
                if template.is_scheduled
                else UNSCHEDULED
            ),
            "last_post_at": last_post.created_at if last_post else None,
            "last_reddit_post_url": (
                last_post.reddit_url or None if last_post else None
            ),
            "last_reminder_at": (
                last_reminder.created_at if last_reminder else None
            ),
            "markdown_problems": markdown_problems(template.content),
        }
    )
    return data


def save_post_settings(
    corporation,
    title: str,
    content: str,
    delivery_method: str,
    posting_day: str | None = None,
) -> RedditPostTemplate:
    """Create or update the corporation's template. A `posting_day` of None
    leaves the day as it is; "" unschedules. Editing the title or body
    withdraws approval: a superuser approved the old words, not the new."""
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
    if posting_day is not None and posting_day not in ("", *DAY_NAMES):
        raise PostSettingsError("invalid_posting_day")
    problems = markdown_problems(typed_content)
    if any(problem["blocking"] for problem in problems):
        raise PostSettingsError("markdown_invalid", problems)

    template = RedditPostTemplate.objects.filter(
        corporation=corporation
    ).first()
    if template is None:
        template = RedditPostTemplate(corporation=corporation)
    elif template.title != title or template.content != content:
        template.approved = False
        template.approved_by = None
        template.approved_at = None
    template.title = title
    template.content = content
    template.delivery_method = delivery_method
    if posting_day is not None:
        template.posting_day = posting_day
    template.save()
    return template
