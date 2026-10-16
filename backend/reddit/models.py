from datetime import time

from django.conf import settings
from django.db import models


class RedditAccount(models.Model):
    """
    A Reddit account a user linked via OAuth so scheduled posts can be
    submitted as them.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reddit_account",
    )
    reddit_username = models.CharField(max_length=64)
    refresh_token = models.TextField()
    scopes = models.JSONField(default=list, blank=True)
    token_invalid = models.BooleanField(
        default=False,
        help_text="Reddit rejected the refresh token; the user must reconnect.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"u/{self.reddit_username}"


class RedditScheduledPost(models.Model):
    """
    A scheduled reddit post.

    Posts without a corporation are alliance posts submitted from the
    alliance Reddit account. Corporation posts are edited by the CEO, who
    picks between a Discord DM reminder and automatic posting from their
    linked Reddit account. Automatic posting needs superuser approval.
    """

    DISCORD_REMINDER = "discord_reminder"
    AUTOMATIC = "automatic"
    DELIVERY_CHOICES = [
        (DISCORD_REMINDER, "Discord DM reminder"),
        (AUTOMATIC, "Automatic post"),
    ]

    corporation = models.OneToOneField(
        "eveonline.EveCorporation",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="reddit_post",
    )
    subreddit = models.CharField(
        max_length=250,
        blank=True,
        help_text="Leave blank to keep a corporation draft unscheduled.",
    )
    title = models.CharField(max_length=250)
    content = models.TextField()

    day_choices = [
        ("monday", "Monday"),
        ("tuesday", "Tuesday"),
        ("wednesday", "Wednesday"),
        ("thursday", "Thursday"),
        ("friday", "Friday"),
        ("saturday", "Saturday"),
        ("sunday", "Sunday"),
    ]

    posting_day = models.CharField(
        max_length=12,
        choices=day_choices,
        blank=True,
        help_text="Leave blank to keep a corporation draft unscheduled.",
    )
    posting_time = models.TimeField(
        default=time(13, 0),
        help_text="EVE time (UTC). Posts go out within 15 minutes of this.",
    )
    delivery_method = models.CharField(
        max_length=20,
        choices=DELIVERY_CHOICES,
        default=DISCORD_REMINDER,
    )
    approved = models.BooleanField(
        default=False,
        help_text=(
            "Superuser approval for automatic posting. Cleared when the CEO "
            "edits the title or content."
        ),
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    last_post_at = models.DateTimeField(null=True, blank=True)
    last_reddit_post_url = models.URLField(
        max_length=500, null=True, blank=True
    )
    last_reddit_post_title = models.CharField(
        max_length=250, null=True, blank=True
    )
    last_reminder_at = models.DateTimeField(null=True, blank=True)
    last_scheduled_on = models.DateField(
        null=True,
        blank=True,
        help_text="Day the scheduler last handled this post (one run per day).",
    )

    discord_channel_id = models.BigIntegerField(null=True, blank=True)
    flair_id = models.CharField(max_length=64, null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    @property
    def is_scheduled(self) -> bool:
        return bool(self.posting_day and self.subreddit)

    def __str__(self):
        return str(self.title)
