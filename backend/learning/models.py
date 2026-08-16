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
