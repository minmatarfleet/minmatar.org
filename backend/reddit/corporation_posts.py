"""The CEO's view of their corporation's scheduled Reddit post."""

from django.utils import timezone

from discord.models import DiscordUser
from reddit.markdown import check_reddit_markdown
from reddit.models import RedditAccount, RedditScheduledPost
from reddit.scheduling import automatic_blocker, next_slot

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


def post_settings(corporation, user) -> dict:
    post = RedditScheduledPost.objects.filter(corporation=corporation).first()
    account = RedditAccount.objects.filter(user=user).first()
    discord_linked = DiscordUser.objects.filter(user=user).exists()
    data = {
        "corporation_id": corporation.corporation_id,
        "exists": post is not None,
        "title": "",
        "content": "",
        "delivery_method": RedditScheduledPost.DISCORD_REMINDER,
        "subreddit": "",
        "posting_day": "",
        "posting_time": "",
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
    if post is None:
        return data
    data.update(
        {
            "title": post.title,
            "content": post.content,
            "delivery_method": post.delivery_method,
            "subreddit": post.subreddit,
            "posting_day": post.posting_day,
            "posting_time": post.posting_time.strftime("%H:%M"),
            "next_run_at": next_slot(post, timezone.now()),
            "approved": post.approved,
            "approved_at": post.approved_at,
            "automatic_status": (
                (automatic_blocker(post) or READY)
                if post.is_scheduled
                else UNSCHEDULED
            ),
            "last_post_at": post.last_post_at,
            "last_reddit_post_url": post.last_reddit_post_url,
            "last_reminder_at": post.last_reminder_at,
            "markdown_problems": markdown_problems(post.content),
        }
    )
    return data


def save_post_settings(
    corporation, title: str, content: str, delivery_method: str
) -> RedditScheduledPost:
    """Create or update the corporation's post. Editing the title or body
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
    if delivery_method not in dict(RedditScheduledPost.DELIVERY_CHOICES):
        raise PostSettingsError("invalid_delivery_method")
    problems = markdown_problems(typed_content)
    if any(problem["blocking"] for problem in problems):
        raise PostSettingsError("markdown_invalid", problems)

    post = RedditScheduledPost.objects.filter(corporation=corporation).first()
    if post is None:
        post = RedditScheduledPost(corporation=corporation)
    elif post.title != title or post.content != content:
        post.approved = False
        post.approved_by = None
        post.approved_at = None
    post.title = title
    post.content = content
    post.delivery_method = delivery_method
    post.save()
    return post
