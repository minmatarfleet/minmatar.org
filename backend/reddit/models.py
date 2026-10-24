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

    The CEO writes the title and body, can pause it, and chooses how it goes
    out: posted automatically as the alliance account (the default), posted
    automatically from their own linked Reddit account, or a Discord DM
    reminder. Either automatic method needs superuser approval. Alliance admins
    pick the subreddit, priority, posting window, flair and Discord channel.
    When the post goes out is decided by the alliance rotation
    (`RedditSchedule`); each slot is a `RedditPost` row.
    """

    ALLIANCE = "alliance"
    AUTOMATIC = "automatic"
    DISCORD_REMINDER = "discord_reminder"
    DELIVERY_CHOICES = [
        (ALLIANCE, "Automatic post as the alliance account"),
        (AUTOMATIC, "Automatic post from the CEO's account"),
        (DISCORD_REMINDER, "Discord DM reminder"),
    ]
    AUTOMATIC_METHODS = (ALLIANCE, AUTOMATIC)

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

    HIGH = "high"
    NORMAL = "normal"
    PRIORITY_CHOICES = [
        (HIGH, "High (about twice as often)"),
        (NORMAL, "Normal"),
    ]
    priority = models.CharField(
        max_length=12,
        choices=PRIORITY_CHOICES,
        default=NORMAL,
        help_text=(
            "Set by alliance admins. Takes effect from the next draft month; "
            "published months don't move."
        ),
    )
    paused = models.BooleanField(
        default=False,
        help_text="Out of the rotation. The CEO can pause and resume.",
    )

    ANY_TIME = "any"
    EU_TIME = "eu"
    US_TIME = "us"
    WINDOW_CHOICES = [
        (ANY_TIME, "Any (11:30-02:00 EVE)"),
        (EU_TIME, "EU (11:30-21:00 EVE)"),
        (US_TIME, "US (18:00-02:00 EVE)"),
    ]
    posting_window = models.CharField(
        max_length=8,
        choices=WINDOW_CHOICES,
        default=ANY_TIME,
        help_text="When in the day this corporation's posts may go out.",
    )
    delivery_method = models.CharField(
        max_length=20,
        choices=DELIVERY_CHOICES,
        default=ALLIANCE,
    )
    approved = models.BooleanField(
        default=False,
        help_text=(
            "Superuser approval of this title and content for automatic "
            "posting. Once approved, the CEO's edits wait as a change "
            "request and the approved words keep going out."
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
    def in_rotation(self) -> bool:
        """Whether the rotation gives this post slots."""
        return bool(
            not self.paused and self.subreddit and self.title and self.content
        )

    def __str__(self):
        return str(self.title)


class RedditPostChangeRequest(models.Model):
    """
    A CEO's title and body waiting for a superuser.

    Once a template is approved, the CEO's edits land here instead of on the
    template, so the approved words keep going out until a superuser
    approves the change. A template that was never approved takes the CEO's
    edits straight away and also gets a request, so it shows up for review.
    Autosave updates the one pending request in place.
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
        (WITHDRAWN, "Withdrawn"),
    ]

    template = models.ForeignKey(
        RedditPostTemplate,
        on_delete=models.CASCADE,
        related_name="change_requests",
    )
    title = models.CharField(max_length=250)
    content = models.TextField()
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default=PENDING
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    notified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When reviewers were last told about it on Discord.",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(
        max_length=500,
        blank=True,
        help_text="Shown to the CEO when a change is rejected.",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["template"],
                condition=models.Q(status="pending"),
                name="reddit_one_pending_change_per_template",
            )
        ]

    def __str__(self):
        return f"{self.template} ({self.get_status_display()})"


class RedditSchedule(models.Model):
    """
    One month of the alliance Reddit rotation.

    A draft is worked out from the templates in the rotation and repaired,
    not rebuilt, when one of them changes, so its estimates hold still. On
    publishing, its slots are confirmed and stop moving except by an admin.
    `weights` and `quotas` record who was in the rotation and how many slots
    each got, which is what later months' fair share is measured against.
    """

    DRAFT = "draft"
    PUBLISHED = "published"
    STATUS_CHOICES = [(DRAFT, "Draft"), (PUBLISHED, "Published")]

    month = models.DateField(unique=True, help_text="First day of the month.")
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default=DRAFT
    )
    weights = models.JSONField(
        default=dict, blank=True, help_text="Template id -> weight."
    )
    quotas = models.JSONField(
        default=dict, blank=True, help_text="Template id -> slots this month."
    )
    inputs_hash = models.CharField(max_length=64, blank=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        ordering = ["-month"]

    @property
    def is_published(self) -> bool:
        return self.status == self.PUBLISHED

    def __str__(self):
        return f"{self.month:%B %Y} ({self.get_status_display()})"


class RedditPost(models.Model):
    """
    One rotation slot, or a post an admin submitted by hand.

    A slot is a draft until its month is published, then confirmed until it
    comes due. The scheduler claims it by moving it from confirmed to
    pending, so two overlapping runs cannot both deliver it.
    """

    DRAFT = "draft"
    CONFIRMED = "confirmed"
    PENDING = "pending"
    POSTED = "posted"
    REMINDED = "reminded"
    FAILED = "failed"
    SKIPPED = "skipped"
    STATUS_CHOICES = [
        (DRAFT, "Draft"),
        (CONFIRMED, "Confirmed"),
        (PENDING, "Sending"),
        (POSTED, "Posted to Reddit"),
        (REMINDED, "CEO reminded on Discord"),
        (FAILED, "Failed"),
        (SKIPPED, "Skipped"),
    ]

    template = models.ForeignKey(
        RedditPostTemplate, on_delete=models.CASCADE, related_name="posts"
    )
    schedule = models.ForeignKey(
        RedditSchedule,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="slots",
    )
    slot_date = models.DateField(
        null=True,
        blank=True,
        unique=True,
        help_text="The rotation slot. Blank when submitted by hand.",
    )
    scheduled_for = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the slot goes out. Blank when submitted by hand.",
    )
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default=PENDING
    )
    fallback_reason = models.CharField(
        max_length=32,
        blank=True,
        help_text=(
            "Why an automatic post went out as a reminder instead, or why "
            "the slot was skipped."
        ),
    )
    title = models.CharField(
        max_length=300, blank=True, help_text="The title as sent."
    )
    reddit_url = models.URLField(max_length=500, blank=True)
    heads_up_sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.template} ({self.get_status_display()})"


class RedditScheduleChange(models.Model):
    """A slot that changed hands after its month was first drafted."""

    ROTATION = "rotation"
    PAUSED = "paused"
    ADMIN = "admin"
    REASON_CHOICES = [
        (ROTATION, "The rotation changed"),
        (PAUSED, "Its corporation paused"),
        (ADMIN, "Moved by an admin"),
    ]

    schedule = models.ForeignKey(
        RedditSchedule, on_delete=models.CASCADE, related_name="changes"
    )
    slot_date = models.DateField()
    from_template = models.ForeignKey(
        RedditPostTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    to_template = models.ForeignKey(
        RedditPostTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    reason = models.CharField(max_length=12, choices=REASON_CHOICES)
    detail = models.CharField(
        max_length=300, blank=True, help_text="For admins: what changed."
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at", "slot_date"]

    def __str__(self):
        return f"{self.slot_date}: {self.get_reason_display()}"
