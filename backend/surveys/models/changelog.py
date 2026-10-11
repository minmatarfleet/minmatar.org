from django.db import models


class SurveyChangelogEntry(models.Model):
    """Leadership-authored "You said → We did" entry, shown to members on the
    following campaign to close the feedback loop."""

    campaign = models.ForeignKey(
        "surveys.SurveyCampaign",
        on_delete=models.CASCADE,
        related_name="changelog_entries",
    )
    heading = models.CharField(max_length=200)
    body_markdown = models.TextField(blank=True)
    published = models.BooleanField(default=False, db_index=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "created_at"]
        verbose_name_plural = "Survey changelog entries"

    def __str__(self):
        return str(self.heading)
