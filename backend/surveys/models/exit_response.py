from django.db import models

from surveys.models.exit_invite import ExitSurveyInvite


class ExitSurveyResponse(models.Model):
    """One submitted exit or alliance move survey (#3198)."""

    invite = models.OneToOneField(
        ExitSurveyInvite, on_delete=models.CASCADE, related_name="response"
    )
    # The corporation they left, so ratings compare across corporations.
    corporation_id = models.BigIntegerField(db_index=True)
    definition_key = models.CharField(max_length=32)
    definition_version = models.PositiveIntegerField()
    submitted_at = models.DateTimeField()

    def __str__(self):
        return f"{self.definition_key} response {self.pk}"


class ExitSurveyAnswer(models.Model):
    """One answer, typed like ``SurveyAnswer``."""

    response = models.ForeignKey(
        ExitSurveyResponse, on_delete=models.CASCADE, related_name="answers"
    )
    question_key = models.CharField(max_length=64, db_index=True)
    numeric_value = models.FloatField(null=True, blank=True)
    text_value = models.TextField(blank=True)
    choice_value = models.CharField(max_length=255, blank=True)
    json_value = models.JSONField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["response", "question_key"],
                name="unique_exit_answer_per_question",
            )
        ]

    def __str__(self):
        return f"{self.question_key} ({self.response_id})"
