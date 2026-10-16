"""When corporation Reddit posts are due, and how each one is delivered.

Each weekly slot is delivered at most once: the scheduler claims it by
inserting a `RedditPost` for (template, slot), which is unique, so two
overlapping runs cannot both deliver it.
"""

import logging
from datetime import datetime, timedelta, timezone as dt_timezone

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from app.errors import create_error_id
from discord.client import DiscordClient
from discord.models import DiscordUser
from eveonline.helpers.corporations.permissions import ceo_user
from eveonline.helpers.corporations.slugs import corporation_slug
from reddit.client import RedditClient, normalize_subreddit
from reddit.models import RedditAccount, RedditPost, RedditPostTemplate

logger = logging.getLogger(__name__)

DAY_NAMES = [day for day, _ in RedditPostTemplate.day_choices]

# A slot missed by more than this (e.g. workers down) is skipped rather than
# posted late.
CATCH_UP_WINDOW = timedelta(hours=12)

# Why an automatic post fell back to a reminder.
NOT_APPROVED = "not_approved"
NO_ACCOUNT = "no_account"
ACCOUNT_INVALID = "account_invalid"
POST_FAILED = "post_failed"

DISCORD_MESSAGE_LIMIT = 2000


def latest_slot(
    template: RedditPostTemplate, now: datetime
) -> datetime | None:
    """The most recent posting slot at or before `now` (UTC)."""
    if template.posting_day not in DAY_NAMES:
        return None
    days_back = (now.weekday() - DAY_NAMES.index(template.posting_day)) % 7
    slot = datetime.combine(
        now.date() - timedelta(days=days_back),
        template.posting_time,
        tzinfo=dt_timezone.utc,
    )
    if slot > now:
        slot -= timedelta(days=7)
    return slot


def _last_handled_at(template: RedditPostTemplate) -> datetime | None:
    if hasattr(template, "last_handled_at"):
        return template.last_handled_at
    return template.posts.aggregate(Max("created_at"))["created_at__max"]


def next_slot(template: RedditPostTemplate, now: datetime) -> datetime | None:
    """The next slot the scheduler will act on, or None if unscheduled."""
    if not template.is_scheduled:
        return None
    slot = latest_slot(template, now)
    if slot is None:
        return None
    if _slot_pending(template, slot, now):
        return slot
    return slot + timedelta(days=7)


def _slot_pending(
    template: RedditPostTemplate, slot: datetime, now: datetime
) -> bool:
    if now - slot > CATCH_UP_WINDOW:
        return False
    # Claimed by an earlier run, or posted by hand since the slot.
    last_handled_at = _last_handled_at(template)
    return last_handled_at is None or last_handled_at < slot


def due_posts(now: datetime) -> list[tuple[RedditPostTemplate, datetime]]:
    due = []
    templates = (
        RedditPostTemplate.objects.exclude(posting_day="")
        .exclude(subreddit="")
        .annotate(last_handled_at=Max("posts__created_at"))
    )
    for template in templates:
        slot = latest_slot(template, now)
        if slot and _slot_pending(template, slot, now):
            due.append((template, slot))
    return due


def claim(
    template: RedditPostTemplate, slot: datetime, now: datetime
) -> RedditPost | None:
    """The new pending post for this slot, or None if another run has it."""
    try:
        with transaction.atomic():
            return RedditPost.objects.create(
                template=template, scheduled_for=slot, created_at=now
            )
    except IntegrityError:
        return None


def run_scheduled_posts(now: datetime | None = None) -> list[str]:
    """Deliver every post whose slot has arrived. Returns the outcomes."""
    now = now or timezone.now()
    outcomes = []
    for template, slot in due_posts(now):
        post = claim(template, slot, now)
        if post is None:
            continue
        outcome = deliver(template, post)
        logger.info("Scheduled Reddit post %s: %s", template.pk, outcome)
        outcomes.append(outcome)
    return outcomes


def posting_account(template: RedditPostTemplate) -> RedditAccount | None:
    """The CEO's linked account; corporation posts are submitted as them."""
    user = ceo_user(template.corporation)
    if user is None:
        return None
    return RedditAccount.objects.filter(user=user).first()


def automatic_blocker(template: RedditPostTemplate) -> str | None:
    """Why this post can't be submitted automatically right now, if at all."""
    if not template.approved:
        return NOT_APPROVED
    account = posting_account(template)
    if account is None:
        return NO_ACCOUNT
    if account.token_invalid:
        return ACCOUNT_INVALID
    return None


def reddit_client_for(template: RedditPostTemplate) -> RedditClient:
    """Posts go out as the CEO when they have linked an account; admin
    resubmits without a link go out as the alliance."""
    account = posting_account(template)
    if account is not None and not account.token_invalid:
        return RedditClient(account)
    return RedditClient()


def deliver(template: RedditPostTemplate, post: RedditPost) -> str:
    """Post or remind for a claimed slot. Returns the post's final status."""
    reason = None
    if template.delivery_method == RedditPostTemplate.AUTOMATIC:
        reason = automatic_blocker(template)
        if reason is None:
            submit(template, post=post)
            if post.status == RedditPost.POSTED:
                return post.status
            reason = POST_FAILED
    post.fallback_reason = reason or ""
    post.status = (
        RedditPost.REMINDED
        if send_reminder(template, reason)
        else RedditPost.SKIPPED
    )
    post.save(update_fields=["status", "fallback_reason"])
    return post.status


def submit(
    template: RedditPostTemplate,
    client: RedditClient | None = None,
    post: RedditPost | None = None,
) -> RedditPost:
    """Submit now and record the result on `post` (a new unscheduled post
    when none is given). Its status is posted or failed."""
    title = template.title.replace("{ID}", create_error_id())
    client = client or reddit_client_for(template)
    result = client.submit_post(
        subreddit=template.subreddit,
        title=title,
        content=template.content,
        flair_id=template.flair_id or None,
    )
    if post is None:
        post = RedditPost(template=template)
    post.title = title
    if result and result.get("url"):
        post.status = RedditPost.POSTED
        post.reddit_url = result["url"]
    else:
        post.status = RedditPost.FAILED
    post.save()

    if post.status == RedditPost.POSTED and template.discord_channel_id:
        link_reddit_post_to_discord(template, post.reddit_url, title)
    return post


def link_reddit_post_to_discord(
    template: RedditPostTemplate,
    reddit_post_url: str,
    title: str,
) -> bool:
    """
    Post a message to the template's Discord channel linking to the Reddit
    post. Runs after each Reddit post, or by hand from the admin.
    Returns True if the message was sent, False otherwise.
    """
    channel = template.discord_channel
    if channel is None:
        logger.info(
            "No Discord channel configured for Reddit post template %s",
            template.pk,
        )
        return False
    message = f"**New Reddit post:** {title}\n{reddit_post_url}"
    try:
        DiscordClient().create_message(channel.channel_id, message)
        logger.info(
            "Linked Reddit post to Discord channel %s: %s",
            channel.channel_id,
            title,
        )
        return True
    except Exception as e:
        logger.exception(
            "Failed to link Reddit post to Discord channel %s: %s",
            channel.channel_id,
            e,
        )
        return False


REASON_TEXT = {
    None: "",
    NOT_APPROVED: (
        "Automatic posting is waiting for approval, so please post this one "
        "yourself."
    ),
    NO_ACCOUNT: (
        "Automatic posting needs your Reddit account linked, so please post "
        "this one yourself."
    ),
    ACCOUNT_INVALID: (
        "Reddit no longer accepts your linked account. Reconnect it in "
        "Settings; until then, please post this one yourself."
    ),
    POST_FAILED: (
        "Automatic posting failed this time, so please post this one "
        "yourself."
    ),
}


def settings_url(template: RedditPostTemplate) -> str:
    base = settings.WEB_LINK_URL.rstrip("/")
    slug = corporation_slug(template.corporation.name)
    return f"{base}/alliance/corporations/{slug}/#settings"


def reminder_messages(
    template: RedditPostTemplate, reason: str | None = None
) -> list[str]:
    """The DM, split into Discord-sized messages. Title and body are fenced
    so the markdown can be copied as-is."""
    subreddit = normalize_subreddit(template.subreddit)
    title = template.title.replace("{ID}", create_error_id())
    header = [
        f"**Reddit post reminder: {template.corporation.name}**",
        f"It's time for your post to r/{subreddit}.",
    ]
    if REASON_TEXT.get(reason):
        header.append(REASON_TEXT[reason])
    header += [
        f"Post it here: <https://www.reddit.com/r/{subreddit}/submit>",
        f"Edit it, or change the day or how it's sent: <{settings_url(template)}>",
        "",
        # Reddit's rich text editor would show the Markdown as literal text.
        "**SWITCH TO MARKDOWN MODE IN THE EDITOR FIRST**",
        "**Title**",
        _fence(title),
        "**Body**",
    ]
    messages = ["\n".join(header)]
    body_limit = DISCORD_MESSAGE_LIMIT - len(_fence(""))
    for chunk in _chunks(_defuse_fences(template.content), body_limit):
        messages.append(_fence(chunk))
    return messages


def _fence(text: str) -> str:
    return f"```\n{_defuse_fences(text)}\n```"


def _defuse_fences(text: str) -> str:
    # A literal ``` would close our fence early; a zero-width space keeps
    # it visually the same.
    return text.replace("```", "`\u200b``")


def _chunks(text: str, limit: int) -> list[str]:
    """Split on line breaks where possible so each piece fits `limit`."""
    chunks = []
    current = ""
    for line in text.splitlines(keepends=True):
        while len(line) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        if len(current) + len(line) > limit:
            chunks.append(current)
            current = ""
        current += line
    if current.strip():
        chunks.append(current)
    return [chunk.rstrip("\n") for chunk in chunks] or [""]


def send_reminder(
    template: RedditPostTemplate, reason: str | None = None
) -> bool:
    user = ceo_user(template.corporation)
    discord_user = (
        DiscordUser.objects.filter(user=user).first() if user else None
    )
    if discord_user is None:
        logger.warning(
            "No Discord-linked CEO to remind for Reddit post %s", template.pk
        )
        return False
    client = DiscordClient()
    try:
        for message in reminder_messages(template, reason):
            client.send_dm(str(discord_user.id), message=message)
    except Exception:
        logger.warning(
            "Failed to DM Reddit post reminder %s", template.pk, exc_info=True
        )
        return False
    return True
