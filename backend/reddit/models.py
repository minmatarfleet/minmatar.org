from datetime import time

from django.conf import settings
from django.db import models
from django.utils import timezone


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


class RedditPostTemplate(models.Model):
    """
    A corporation's recurring Reddit recruitment post. Each corporation has
    at most one.

    The CEO writes the title and body, picks the posting day, and chooses
    between a Discord DM reminder and automatic posting from their linked
    Reddit account. Automatic posting needs superuser approval. Alliance
    admins pick the subreddit, time, flair and Discord channel. Every time
    the post comes due a `RedditPost` row records what happened.
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
        related_name="reddit_post_template",
    )
    subreddit = models.CharField(
        max_length=250,
        blank=True,
        default="evejobs",
        help_text="Leave blank to pause the post.",
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
        help_text="Picked by the CEO. Blank means not scheduled.",
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

    discord_channel = models.ForeignKey(
        "discord.DiscordChannel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        limit_choices_to={"channel_type": "text"},
        help_text="Text channel that gets a link after each Reddit post.",
    )
    flair_id = models.CharField(max_length=64, null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    @property
    def is_scheduled(self) -> bool:
        return bool(self.posting_day and self.subreddit)

    def __str__(self):
        return str(self.title)


class RedditPost(models.Model):
    """
    One occurrence of a template: a scheduled slot that was posted or
    reminded, or a post an admin submitted by hand.

    The unique (template, scheduled_for) pair is how the scheduler claims a
    slot, so two overlapping runs cannot both deliver it.
    """

    PENDING = "pending"
    POSTED = "posted"
    REMINDED = "reminded"
    FAILED = "failed"
    SKIPPED = "skipped"
    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (POSTED, "Posted to Reddit"),
        (REMINDED, "CEO reminded on Discord"),
        (FAILED, "Failed"),
        (SKIPPED, "Skipped"),
    ]

    template = models.ForeignKey(
        RedditPostTemplate, on_delete=models.CASCADE, related_name="posts"
    )
    scheduled_for = models.DateTimeField(
        null=True,
        blank=True,
        help_text="The slot this was for. Blank when submitted by hand.",
    )
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default=PENDING
    )
    fallback_reason = models.CharField(
        max_length=32,
        blank=True,
        help_text="Why an automatic post went out as a reminder instead.",
    )
    title = models.CharField(
        max_length=300, blank=True, help_text="The title as sent."
    )
    reddit_url = models.URLField(max_length=500, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["template", "scheduled_for"],
                name="reddit_post_one_per_slot",
            )
        ]

    def __str__(self):
        return f"{self.template} ({self.get_status_display()})"
