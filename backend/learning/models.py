from django.contrib.auth.models import User
from django.db import models


class Persona(models.TextChoices):
    ALLIANCE = "alliance", "Alliance"
    MILITIA = "militia", "Militia"
    OTHER = "other", "Other"


class ContentKind(models.TextChoices):
    GUIDE = "guide", "Guide"
    BLOG = "blog", "Blog"
    PAGE = "page", "Page"
    YOUTUBE = "youtube", "YouTube"
    EXTERNAL = "external", "External"
    MENTOR_CLASS = "mentor_class", "Class with a mentor"
    OTHER = "other", "Other"


class Learning(models.Model):
    """Abstract unit of content that points at a destination URL."""

    slug = models.SlugField(max_length=100, unique=True)
    title = models.CharField(max_length=250)
    summary = models.TextField(blank=True, default="")
    url = models.CharField(
        max_length=500,
        help_text="Site-relative path (e.g. /learning/guides/…) or absolute URL.",
    )
    content_kind = models.CharField(
        max_length=20,
        choices=ContentKind.choices,
        default=ContentKind.GUIDE,
    )
    thumbnail_url = models.URLField(blank=True, default="")
    estimated_minutes = models.PositiveIntegerField(null=True, blank=True)
    published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title


class Certificate(models.Model):
    """Ordered group of learnings; awarded when all are completed."""

    slug = models.SlugField(max_length=100, unique=True)
    title = models.CharField(max_length=250)
    summary = models.TextField(blank=True, default="")
    published = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    personas = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "List of persona keys that include this certificate by default "
            '(e.g. ["alliance", "militia"]).'
        ),
    )
    learnings = models.ManyToManyField(
        Learning,
        through="CertificateLearning",
        related_name="certificates",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "title"]

    def __str__(self):
        return self.title


class CertificateLearning(models.Model):
    certificate = models.ForeignKey(
        Certificate,
        on_delete=models.CASCADE,
        related_name="certificate_learnings",
    )
    learning = models.ForeignKey(
        Learning,
        on_delete=models.CASCADE,
        related_name="certificate_links",
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=("certificate", "learning"),
                name="uniq_certificate_learning",
            ),
        ]

    def __str__(self):
        return f"{self.certificate.slug} · {self.learning.slug} ({self.order})"


class UserLearningPreference(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="learning_preference",
    )
    persona = models.CharField(
        max_length=20,
        choices=Persona.choices,
        default=Persona.OTHER,
    )
    persona_confirmed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} · {self.persona}"


class UserLearningProgress(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="learning_progress",
    )
    learning = models.ForeignKey(
        Learning,
        on_delete=models.CASCADE,
        related_name="user_progress",
    )
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "User learning progress"
        constraints = [
            models.UniqueConstraint(
                fields=("user", "learning"),
                name="uniq_user_learning_progress",
            ),
        ]

    def __str__(self):
        return f"{self.user.username} · {self.learning.slug}"


class UserCertificateAward(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="certificate_awards",
    )
    certificate = models.ForeignKey(
        Certificate,
        on_delete=models.CASCADE,
        related_name="awards",
    )
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("user", "certificate"),
                name="uniq_user_certificate_award",
            ),
        ]

    def __str__(self):
        return f"{self.user.username} · {self.certificate.slug}"


# --------------------------------------------------------------- mentors
# One-to-one classes: a pilot asks a mentor for a class, the mentor picks a
# time inside both pilots' times, the bot introduces them by DM, reminds
# both a day before and asks each for private feedback two days after.
# See docs/learning/mentors.md.


def _empty_list():
    return []


class MentorProfile(models.Model):
    """A pilot who mentors (or asked to), and when they are around."""

    STATUS_APPLIED = "applied"
    STATUS_APPROVED = "approved"
    STATUS_DECLINED = "declined"
    STATUS_REMOVED = "removed"
    STATUS_CHOICES = [
        (STATUS_APPLIED, "Asked to mentor"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_DECLINED, "Declined"),
        (STATUS_REMOVED, "Removed"),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="mentor_profile"
    )
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_APPLIED
    )
    application_note = models.TextField(blank=True, default="")
    # Timezone bracket codes (timezones.brackets) and evening weekdays
    # (0 = Monday ... 6 = Sunday) on the bracket's own clock.
    weekday_brackets = models.JSONField(default=_empty_list, blank=True)
    weekend_brackets = models.JSONField(default=_empty_list, blank=True)
    days = models.JSONField(default=_empty_list, blank=True)
    classes_per_week = models.PositiveSmallIntegerField(default=2)
    taking_requests = models.BooleanField(default=True)
    decided_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} · {self.status}"

    @property
    def approved(self) -> bool:
        return self.status == self.STATUS_APPROVED


class MentorClass(models.Model):
    """A class a mentor wrote. Several mentors can teach it."""

    STATUS_DRAFT = "draft"
    STATUS_REVIEW = "review"
    STATUS_PUBLISHED = "published"
    STATUS_HIDDEN = "hidden"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_REVIEW, "Waiting for review"),
        (STATUS_PUBLISHED, "Published"),
        (STATUS_HIDDEN, "Hidden"),
    ]

    WHERE_VOICE = "voice"
    WHERE_SCREEN_SHARE = "screen_share"
    WHERE_IN_SPACE = "in_space"
    WHERE_CHOICES = [
        (WHERE_VOICE, "Voice"),
        (WHERE_SCREEN_SHARE, "Screen share"),
        (WHERE_IN_SPACE, "In space"),
    ]

    slug = models.SlugField(max_length=100, unique=True)
    title = models.CharField(max_length=120)
    summary = models.TextField(blank=True, default="")
    outline = models.TextField(
        blank=True, default="", help_text="What you'll learn, one per line."
    )
    minutes = models.PositiveSmallIntegerField(default=60)
    where = models.CharField(
        max_length=16, choices=WHERE_CHOICES, default=WHERE_VOICE
    )
    # [{"kind": "alliance_days", "value": "7"}, ...]; see mentors/requirements.py
    requirements = models.JSONField(default=_empty_list, blank=True)
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT
    )
    author = models.ForeignKey(
        User,
        null=True,
        on_delete=models.SET_NULL,
        related_name="authored_mentor_classes",
    )
    learning = models.OneToOneField(
        Learning,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mentor_class",
    )
    review_note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return str(self.title)


class MentorClassTeacher(models.Model):
    """A mentor teaching a class: the author, or a mentor they invited."""

    STATUS_INVITED = "invited"
    STATUS_ACCEPTED = "accepted"
    STATUS_CHOICES = [
        (STATUS_INVITED, "Invited"),
        (STATUS_ACCEPTED, "Accepted"),
    ]

    mentor_class = models.ForeignKey(
        MentorClass, on_delete=models.CASCADE, related_name="teachers"
    )
    mentor = models.ForeignKey(
        MentorProfile, on_delete=models.CASCADE, related_name="teaching"
    )
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_ACCEPTED
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("mentor_class", "mentor"),
                name="uniq_mentor_class_teacher",
            ),
        ]

    def __str__(self):
        return f"{self.mentor_class.slug} · {self.mentor.user.username}"


class MentorRequest(models.Model):
    """One pilot asking one mentor for one class, through to its outcome."""

    STATUS_ASKED = "asked"
    STATUS_BOOKED = "booked"
    STATUS_PASSED = "passed"
    STATUS_EXPIRED = "expired"
    STATUS_CANCELLED = "cancelled"
    STATUS_DONE = "done"
    STATUS_NO_SHOW = "no_show"
    STATUS_UNCONFIRMED = "unconfirmed"
    STATUS_CHOICES = [
        (STATUS_ASKED, "Asked"),
        (STATUS_BOOKED, "Booked"),
        (STATUS_PASSED, "Passed to another mentor"),
        (STATUS_EXPIRED, "No mentor could take it"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_DONE, "Done"),
        (STATUS_NO_SHOW, "No-show"),
        (STATUS_UNCONFIRMED, "Closed unconfirmed"),
    ]
    OPEN_STATUSES = (STATUS_ASKED, STATUS_BOOKED)

    RATING_REALLY = "really"
    RATING_BIT = "bit"
    RATING_NOT = "not"
    RATING_DIDNT_HAPPEN = "didnt_happen"
    RATING_CHOICES = [
        (RATING_REALLY, "Really helped"),
        (RATING_BIT, "Helped a bit"),
        (RATING_NOT, "Didn't help"),
        (RATING_DIDNT_HAPPEN, "It didn't happen"),
    ]

    OUTCOME_DONE = "done"
    OUTCOME_ANOTHER = "another"
    OUTCOME_NO_SHOW = "no_show"
    OUTCOME_MOVED = "moved"
    OUTCOME_CHOICES = [
        (OUTCOME_DONE, "Yes, done"),
        (OUTCOME_ANOTHER, "Yes, needs another class"),
        (OUTCOME_NO_SHOW, "No-show"),
        (OUTCOME_MOVED, "We moved it"),
    ]

    pilot = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="mentor_requests"
    )
    mentor = models.ForeignKey(
        MentorProfile, on_delete=models.CASCADE, related_name="requests"
    )
    mentor_class = models.ForeignKey(
        MentorClass, on_delete=models.CASCADE, related_name="requests"
    )
    note = models.TextField(blank=True, default="")
    weekday_brackets = models.JSONField(default=_empty_list, blank=True)
    weekend_brackets = models.JSONField(default=_empty_list, blank=True)
    days = models.JSONField(default=_empty_list, blank=True)
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_ASKED
    )
    passed_from = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="passed_to",
    )
    starts_at = models.DateTimeField(null=True, blank=True, db_index=True)
    bring = models.CharField(max_length=200, blank=True, default="")
    answered_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    reminded_at = models.DateTimeField(null=True, blank=True)
    pilot_confirmed_at = models.DateTimeField(null=True, blank=True)
    mentor_confirmed_at = models.DateTimeField(null=True, blank=True)
    followed_up_at = models.DateTimeField(null=True, blank=True)
    pilot_rating = models.CharField(
        max_length=16, choices=RATING_CHOICES, blank=True, default=""
    )
    pilot_note = models.TextField(blank=True, default="")
    pilot_answered_at = models.DateTimeField(null=True, blank=True)
    mentor_outcome = models.CharField(
        max_length=16, choices=OUTCOME_CHOICES, blank=True, default=""
    )
    mentor_notes = models.TextField(blank=True, default="")
    mentor_answered_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["status", "starts_at"],
                name="mentor_req_status_starts",
            ),
        ]

    def __str__(self):
        return (
            f"{self.pilot.username} → {self.mentor.user.username} · "
            f"{self.mentor_class.slug} ({self.status})"
        )
