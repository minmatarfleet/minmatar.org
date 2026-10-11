from django.db import models


class SurveyQuestionAggregate(models.Model):
    """Pre-computed distribution for one question within one segment of one
    campaign. Powers the leadership results view without re-scanning raw
    responses on every request."""

    campaign = models.ForeignKey(
        "surveys.SurveyCampaign",
        on_delete=models.CASCADE,
        related_name="aggregates",
    )
    question_key = models.CharField(max_length=64, db_index=True)
    # "all", "corp:A-RAT", "cohort:<30d", "tier:core", ...
    segment_key = models.CharField(max_length=64, default="all", db_index=True)

    n = models.PositiveIntegerField(default=0)
    mean = models.FloatField(null=True, blank=True)
    # {value: count} for scale/choice, or {row: {option: count}} for matrix.
    distribution = models.JSONField(default=dict)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "question_key", "segment_key"],
                name="unique_aggregate_per_segment",
            )
        ]

    def __str__(self):
        return f"{self.question_key} [{self.segment_key}] n={self.n}"
