from django.contrib.auth.models import User
from django.db import models

from surveys.constants import STATUS_CHOICES, STATUS_DRAFT, STATUS_OPEN


class SurveyCampaign(models.Model):
    """A single quarter's survey instance, bound to a code-defined schema."""

    year = models.PositiveIntegerField()
    quarter = models.PositiveSmallIntegerField(help_text="1-4")
    definition_key = models.CharField(
        max_length=32,
        help_text="Key into surveys.definitions.SURVEY_DEFINITIONS.",
    )
    title = models.CharField(max_length=128)
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        db_index=True,
    )
    opens_at = models.DateTimeField(null=True, blank=True)
    closes_at = models.DateTimeField(null=True, blank=True)
    # Optional one-off ("spotlight") questions specific to this campaign,
    # rendered just before the Open floor. Each item:
    #   {"key": "desktop_app", "type": "single", "label": "...",
    #    "help": "", "choices": ["Yes", "Maybe", "No"], "required": false}
    # type is any survey question type (single/multi/agree/scale5/text).
    spotlight_questions = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year", "-quarter"]
        constraints = [
            models.UniqueConstraint(
                fields=["year", "quarter"], name="unique_survey_per_quarter"
            )
        ]

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    @property
    def is_open(self) -> bool:
        return self.status == STATUS_OPEN
