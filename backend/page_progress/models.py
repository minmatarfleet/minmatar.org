from django.contrib.auth.models import User
from django.db import models


class UserPageProgress(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="page_progress",
    )
    page_key = models.CharField(max_length=255)
    page_title = models.CharField(max_length=255, blank=True, default="")
    version = models.CharField(max_length=128)
    section_total = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "User page progress"
        verbose_name_plural = "User page progress"
        constraints = [
            models.UniqueConstraint(
                fields=("user", "page_key", "version"),
                name="uniq_user_page_progress_version",
            ),
        ]
        indexes = [
            models.Index(fields=("page_key",)),
            models.Index(fields=("user", "page_key")),
        ]

    def __str__(self):
        return f"{self.user.username} · {self.page_key} · {self.version}"

    @property
    def read_count(self) -> int:
        return UserPageSectionProgress.objects.filter(
            user_id=self.user_id,
            page_key=self.page_key,
            version=self.version,
        ).count()

    @property
    def percent(self) -> int:
        if self.section_total <= 0:
            return 0
        return round(100 * self.read_count / self.section_total)

    @property
    def is_acknowledged(self) -> bool:
        return self.acknowledged_at is not None


class UserPageSectionProgress(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="page_section_progress",
    )
    page_key = models.CharField(max_length=255)
    section_id = models.CharField(max_length=255)
    version = models.CharField(max_length=128)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User page section progress"
        verbose_name_plural = "User page section progress"
        constraints = [
            models.UniqueConstraint(
                fields=("user", "page_key", "section_id", "version"),
                name="uniq_user_page_section_progress_version",
            ),
        ]
        indexes = [
            models.Index(fields=("user", "page_key", "version")),
        ]

    def __str__(self):
        return (
            f"{self.user.username} · {self.page_key} · "
            f"{self.section_id} · {self.version}"
        )
