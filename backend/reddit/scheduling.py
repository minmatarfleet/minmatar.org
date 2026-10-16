"""When scheduled Reddit posts are due, and how each one is delivered.

A post is delivered at most once per weekly slot: the scheduler claims the
slot by writing `last_scheduled_on` with a conditional UPDATE, so two
overlapping runs cannot both submit it.
"""

import logging
from datetime import datetime, timedelta, timezone as dt_timezone

from django.conf import settings
from django.utils import timezone

from app.errors import create_error_id
from discord.client import DiscordClient
from discord.models import DiscordUser
from eveonline.helpers.corporations.permissions import ceo_user
from eveonline.helpers.corporations.slugs import corporation_slug
from reddit.client import RedditClient, normalize_subreddit
from reddit.models import RedditAccount, RedditScheduledPost

logger = logging.getLogger(__name__)

DAY_NAMES = [day for day, _ in RedditScheduledPost.day_choices]

# A slot missed by more than this (e.g. workers down) is skipped rather than
# posted late.
CATCH_UP_WINDOW = timedelta(hours=12)

# Why an automatic post fell back to a reminder.
NOT_APPROVED = "not_approved"
NO_ACCOUNT = "no_account"
ACCOUNT_INVALID = "account_invalid"
POST_FAILED = "post_failed"

DISCORD_MESSAGE_LIMIT = 2000


def latest_slot(post: RedditScheduledPost, now: datetime) -> datetime | None:
    """The most recent posting slot at or before `now` (UTC)."""
    if post.posting_day not in DAY_NAMES:
        return None
    days_back = (now.weekday() - DAY_NAMES.index(post.posting_day)) % 7
    slot = datetime.combine(
        now.date() - timedelta(days=days_back),
        post.posting_time,
        tzinfo=dt_timezone.utc,
    )
    if slot > now:
        slot -= timedelta(days=7)
    return slot


def next_slot(post: RedditScheduledPost, now: datetime) -> datetime | None:
    """The next slot the scheduler will act on, or None if unscheduled."""
    if not post.is_scheduled:
        return None
    slot = latest_slot(post, now)
    if slot is None:
        return None
    if _slot_pending(post, slot, now):
        return slot
    return slot + timedelta(days=7)


def _slot_pending(
    post: RedditScheduledPost, slot: datetime, now: datetime
) -> bool:
    if now - slot > CATCH_UP_WINDOW:
        return False
    if post.last_scheduled_on and post.last_scheduled_on >= slot.date():
        return False
    # Posted or reminded by hand (or by the old daily task) since the slot.
    for delivered_at in (post.last_post_at, post.last_reminder_at):
        if delivered_at and delivered_at >= slot:
            return False
    return True


def due_posts(now: datetime) -> list[tuple[RedditScheduledPost, datetime]]:
    due = []
    for post in RedditScheduledPost.objects.exclude(posting_day="").exclude(
        subreddit=""
    ):
        slot = latest_slot(post, now)
        if slot and _slot_pending(post, slot, now):
            due.append((post, slot))
    return due


def claim(post: RedditScheduledPost, slot: datetime) -> bool:
    claimed = (
        RedditScheduledPost.objects.filter(
            pk=post.pk, last_scheduled_on=post.last_scheduled_on
        ).update(last_scheduled_on=slot.date())
        == 1
    )
    if claimed:
        post.last_scheduled_on = slot.date()
    return claimed


def run_scheduled_posts(now: datetime | None = None) -> list[str]:
    """Deliver every post whose slot has arrived. Returns the outcomes."""
    now = now or timezone.now()
    outcomes = []
    for post, slot in due_posts(now):
        if not claim(post, slot):
            continue
        outcome = deliver(post)
        logger.info("Scheduled Reddit post %s: %s", post.pk, outcome)
        outcomes.append(outcome)
    return outcomes


def posting_account(post: RedditScheduledPost) -> RedditAccount | None:
    """The CEO's linked account; corporation posts are submitted as them."""
    if post.corporation is None:
        return None
    user = ceo_user(post.corporation)
    if user is None:
        return None
    return RedditAccount.objects.filter(user=user).first()


def automatic_blocker(post: RedditScheduledPost) -> str | None:
    """Why this post can't be submitted automatically right now, if at all."""
    if not post.approved:
        return NOT_APPROVED
    if post.corporation is None:
        return None
    account = posting_account(post)
    if account is None:
        return NO_ACCOUNT
    if account.token_invalid:
        return ACCOUNT_INVALID
    return None


def reddit_client_for(post: RedditScheduledPost) -> RedditClient:
    """Corporation posts go out as the CEO when they have linked an account;
    alliance posts (and admin resubmits without a link) as the alliance."""
    account = posting_account(post)
    if account is not None and not account.token_invalid:
        return RedditClient(account)
    return RedditClient()


def deliver(post: RedditScheduledPost) -> str:
    reason = None
    if post.delivery_method == RedditScheduledPost.AUTOMATIC:
        reason = automatic_blocker(post)
        if reason is None:
            if submit(post)[1]:
                return "posted"
            reason = POST_FAILED
    if post.corporation is None:
        # Alliance posts have nobody to remind.
        return "skipped"
    return "reminded" if send_reminder(post, reason) else "skipped"


def submit(post: RedditScheduledPost, client: RedditClient | None = None):
    """Submit now and record the result. Returns (title, result), where
    result is the {url, id} dict or None on failure."""
    title = post.title.replace("{ID}", create_error_id())
    client = client or reddit_client_for(post)
    result = client.submit_post(
        subreddit=post.subreddit,
        title=title,
        content=post.content,
        flair_id=post.flair_id or None,
    )
    post.last_post_at = timezone.now()
    fields = ["last_post_at"]
    if result and result.get("url"):
        post.last_reddit_post_url = result["url"]
        post.last_reddit_post_title = title
        fields += ["last_reddit_post_url", "last_reddit_post_title"]
    post.save(update_fields=fields)

    if result and result.get("url") and post.discord_channel_id:
        link_reddit_post_to_discord(post, result["url"], title)
    return title, result


def link_reddit_post_to_discord(
    scheduled_post: RedditScheduledPost,
    reddit_post_url: str,
    title: str,
) -> bool:
    """
    Post a message to the Discord channel attached to the scheduled post,
    linking to the Reddit post. Call this manually or it runs after creating a post.
    Returns True if the message was sent, False otherwise.
    """
    channel_id = scheduled_post.discord_channel_id
    if not channel_id:
        logger.info(
            "No Discord channel configured for scheduled post %s (discord_channel_id=%r)",
            scheduled_post.title,
            scheduled_post.discord_channel_id,
        )
        return False
    message = f"**New Reddit post:** {title}\n{reddit_post_url}"
    try:
        DiscordClient().create_message(channel_id, message)
        logger.info(
            "Linked Reddit post to Discord channel %s: %s",
            channel_id,
            title,
        )
        return True
    except Exception as e:
        logger.exception(
            "Failed to link Reddit post to Discord channel %s: %s",
            channel_id,
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


def settings_url(post: RedditScheduledPost) -> str:
    base = settings.WEB_LINK_URL.rstrip("/")
    slug = corporation_slug(post.corporation.name)
    return f"{base}/alliance/corporations/{slug}/#settings"


def reminder_messages(
    post: RedditScheduledPost, reason: str | None = None
) -> list[str]:
    """The DM, split into Discord-sized messages. Title and body are fenced
    so the markdown can be copied as-is."""
    subreddit = normalize_subreddit(post.subreddit)
    title = post.title.replace("{ID}", create_error_id())
    header = [
        f"**Reddit post reminder: {post.corporation.name}**",
        f"It's time for your post to r/{subreddit}.",
    ]
    if REASON_TEXT.get(reason):
        header.append(REASON_TEXT[reason])
    header += [
        f"Post it here: <https://www.reddit.com/r/{subreddit}/submit>",
        f"Edit it or change how it's sent: <{settings_url(post)}>",
        "",
        "**Title**",
        _fence(title),
        "**Body**",
    ]
    messages = ["\n".join(header)]
    body_limit = DISCORD_MESSAGE_LIMIT - len(_fence(""))
    for chunk in _chunks(_defuse_fences(post.content), body_limit):
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


def send_reminder(post: RedditScheduledPost, reason: str | None = None):
    user = ceo_user(post.corporation)
    discord_user = (
        DiscordUser.objects.filter(user=user).first() if user else None
    )
    if discord_user is None:
        logger.warning(
            "No Discord-linked CEO to remind for Reddit post %s", post.pk
        )
        return False
    client = DiscordClient()
    try:
        for message in reminder_messages(post, reason):
            client.send_dm(str(discord_user.id), message=message)
    except Exception:
        logger.warning(
            "Failed to DM Reddit post reminder %s", post.pk, exc_info=True
        )
        return False
    post.last_reminder_at = timezone.now()
    post.save(update_fields=["last_reminder_at"])
    return True
