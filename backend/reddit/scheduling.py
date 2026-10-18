"""Delivering rotation slots, and the Discord DMs that go with them.

Which corporation gets which slot is `reddit.schedule`'s business; this
module posts or reminds for a slot once it is due, exactly once: the
scheduler claims a confirmed slot by moving it to pending, and only the run
that makes that change delivers it.
"""

import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

from app.errors import create_error_id
from discord.client import DiscordClient
from discord.models import DiscordUser
from discord.outbox import queue_dm
from eveonline.helpers.corporations.permissions import ceo_user
from eveonline.helpers.corporations.slugs import corporation_slug
from reddit.client import RedditClient, normalize_subreddit
from reddit.models import RedditAccount, RedditPost, RedditPostTemplate

logger = logging.getLogger(__name__)

# A slot missed by more than this (e.g. workers down) is skipped rather than
# posted late.
CATCH_UP_WINDOW = timedelta(hours=12)

# Why an automatic post fell back to a reminder.
NOT_APPROVED = "not_approved"
NO_ACCOUNT = "no_account"
ACCOUNT_INVALID = "account_invalid"
POST_FAILED = "post_failed"

DISCORD_MESSAGE_LIMIT = 2000


def claim(post: RedditPost) -> bool:
    """Take a confirmed slot for delivery. False if another run has it."""
    return bool(
        RedditPost.objects.filter(
            pk=post.pk, status=RedditPost.CONFIRMED
        ).update(status=RedditPost.PENDING)
    )


def posting_account(template: RedditPostTemplate) -> RedditAccount | None:
    """The CEO's linked account, when the post goes out as them."""
    if template.delivery_method != RedditPostTemplate.AUTOMATIC:
        return None
    user = ceo_user(template.corporation)
    if user is None:
        return None
    return RedditAccount.objects.filter(user=user).first()


def automatic_blocker(template: RedditPostTemplate) -> str | None:
    """Why this post can't be submitted automatically right now, if at all."""
    if not template.approved:
        return NOT_APPROVED
    if template.delivery_method == RedditPostTemplate.ALLIANCE:
        return None
    account = posting_account(template)
    if account is None:
        return NO_ACCOUNT
    if account.token_invalid:
        return ACCOUNT_INVALID
    return None


def reddit_client_for(template: RedditPostTemplate) -> RedditClient:
    """Posts go out as the CEO when they chose their own linked account;
    everything else (including admin resubmits without a link) goes out as
    the alliance."""
    account = posting_account(template)
    if account is not None and not account.token_invalid:
        return RedditClient(account)
    return RedditClient()


def deliver(
    template: RedditPostTemplate,
    post: RedditPost,
    now: datetime | None = None,
) -> str:
    """Post or remind for a claimed slot. Returns the post's final status."""
    post.delivered_at = now or timezone.now()
    reason = None
    if template.delivery_method in RedditPostTemplate.AUTOMATIC_METHODS:
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
    post.save(update_fields=["status", "fallback_reason", "delivered_at"])
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
    post.delivered_at = post.delivered_at or timezone.now()
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
        f"Edit it, pause it, or change how it's sent: <{settings_url(template)}>",
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
    return dm_ceo(template, reminder_messages(template, reason))


def _ceo_discord_user(template: RedditPostTemplate) -> DiscordUser | None:
    user = ceo_user(template.corporation)
    discord_user = (
        DiscordUser.objects.filter(user=user).first() if user else None
    )
    if discord_user is None:
        logger.warning(
            "No Discord-linked CEO to DM for Reddit post %s", template.pk
        )
    return discord_user


def dm_ceo(template: RedditPostTemplate, messages: list[str]) -> bool:
    """DM the corporation's CEO. False if they have no Discord or it fails.

    Sends inline: callers run in Celery and record whether it worked. From a
    web request (the admin), use dm_ceo_later.
    """
    discord_user = _ceo_discord_user(template)
    if discord_user is None:
        return False
    client = DiscordClient()
    try:
        for message in messages:
            client.send_dm(str(discord_user.id), message=message)
    except Exception:
        logger.warning(
            "Failed to DM about Reddit post %s", template.pk, exc_info=True
        )
        return False
    return True


def dm_ceo_later(template: RedditPostTemplate, messages: list[str]) -> bool:
    """Queue the same DMs as dm_ceo for a worker; False if there is no CEO
    on Discord to send them to."""
    discord_user = _ceo_discord_user(template)
    if discord_user is None:
        return False
    queue_dm(
        discord_user.id,
        messages=messages,
        context=f"Reddit post {template.pk} CEO DM",
    )
    return True


def eve_time(when: datetime) -> str:
    """e.g. "Tue 3 Nov at 14:20 EVE"."""
    return f"{when:%a} {when.day} {when:%b} at {when:%H:%M} EVE"


def _subreddit(template: RedditPostTemplate) -> str:
    return f"r/{normalize_subreddit(template.subreddit)}"


def heads_up_message(template: RedditPostTemplate, when: datetime) -> str:
    return "\n".join(
        [
            f"**Reddit post tomorrow: {template.corporation.name}**",
            f"Your post to {_subreddit(template)} is due {eve_time(when)}. "
            "We'll DM it to you ready to copy.",
            f"Want to freshen it up first? <{settings_url(template)}>",
        ]
    )


def extra_slot_message(template: RedditPostTemplate, when: datetime) -> str:
    return "\n".join(
        [
            f"**Extra Reddit slot: {template.corporation.name}**",
            f"A slot opened up in the rotation: your post to "
            f"{_subreddit(template)} is now also due {eve_time(when)}.",
            f"See your schedule: <{settings_url(template)}>",
        ]
    )


def slot_removed_message(template: RedditPostTemplate, when: datetime) -> str:
    return "\n".join(
        [
            f"**Reddit slot moved: {template.corporation.name}**",
            f"An alliance admin moved your {eve_time(when)} post to another "
            "corporation.",
            f"See your schedule: <{settings_url(template)}>",
        ]
    )


def slot_moved_message(
    template: RedditPostTemplate, old: datetime, new: datetime
) -> str:
    return "\n".join(
        [
            f"**Reddit slot moved: {template.corporation.name}**",
            f"Your post to {_subreddit(template)} moved from {eve_time(old)} "
            f"to {eve_time(new)}.",
            f"See your schedule: <{settings_url(template)}>",
        ]
    )
