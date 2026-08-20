from django.db import models


class SurveyAnswer(models.Model):
    """One answer keyed by the stable question_key. Values are stored typed so
    aggregation never has to parse free text for numeric questions."""

    response = models.ForeignKey(
        "surveys.SurveyResponse",
        on_delete=models.CASCADE,
        related_name="answers",
    )
    question_key = models.CharField(max_length=64, db_index=True)

    numeric_value = models.FloatField(null=True, blank=True)
    text_value = models.TextField(blank=True)
    choice_value = models.CharField(max_length=255, blank=True)
    json_value = models.JSONField(null=True, blank=True)  # matrix / multi

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["response", "question_key"],
                name="unique_answer_per_question",
            )
        ]

    def __str__(self):
        return f"{self.question_key} ({self.response_id})"
