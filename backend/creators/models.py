from django.conf import settings
from django.db import models


class CreatorProvider(models.TextChoices):
    TWITCH = "twitch", "Twitch"
    YOUTUBE = "youtube", "YouTube"
    REDDIT = "reddit", "Reddit"


class CreatorItemKind(models.TextChoices):
    VIDEO = "video", "Video"
    VOD = "vod", "VOD"
    STREAM = "stream", "Stream"
    REDDIT_POST = "reddit_post", "Reddit post"


class CreatorAccount(models.Model):
    """OAuth-linked Twitch / YouTube / Reddit account for a Thinkspeak creator."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="creator_accounts",
    )
    provider = models.CharField(max_length=16, choices=CreatorProvider.choices)
    platform_user_id = models.CharField(max_length=128)
    platform_username = models.CharField(max_length=255, blank=True)

    access_token = models.TextField(blank=True)
    refresh_token = models.TextField(blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    scopes = models.JSONField(default=list, blank=True)
    extra = models.JSONField(default=dict, blank=True)
    token_invalid = models.BooleanField(default=False)

    is_live = models.BooleanField(default=False)
    live_started_at = models.DateTimeField(null=True, blank=True)
    live_title = models.CharField(max_length=512, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "provider"],
                name="creators_account_user_provider_uniq",
            ),
            models.UniqueConstraint(
                fields=["provider", "platform_user_id"],
                name="creators_account_provider_platform_uniq",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.provider}:{self.platform_username or self.platform_user_id}"


class CreatorItem(models.Model):
    """Ingested media item from a linked creator account."""

    account = models.ForeignKey(
        CreatorAccount,
        on_delete=models.CASCADE,
        related_name="items",
    )
    provider = models.CharField(max_length=16, choices=CreatorProvider.choices)
    external_id = models.CharField(max_length=128)
    kind = models.CharField(max_length=16, choices=CreatorItemKind.choices)
    title = models.CharField(max_length=512, blank=True)
    url = models.URLField(max_length=1024, blank=True)
    thumbnail_url = models.URLField(max_length=1024, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "external_id"],
                name="creators_item_provider_external_uniq",
            ),
        ]
        ordering = ["-published_at", "-id"]

    def __str__(self) -> str:
        return f"{self.provider}:{self.kind}:{self.title or self.external_id}"
