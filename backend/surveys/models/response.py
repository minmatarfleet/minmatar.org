from django.contrib.auth.models import User
from django.db import models


class SurveyResponse(models.Model):
    """A member's non-anonymous response, with segmentation snapshotted at
    submission time so trends stay comparable even as members change corp/tribe.
    """

    campaign = models.ForeignKey(
        "surveys.SurveyCampaign",
        on_delete=models.CASCADE,
        related_name="responses",
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="survey_responses"
    )
    submitted_at = models.DateTimeField(auto_now_add=True)

    # --- Snapshotted segmentation dimensions (frozen at submit) ---
    corporation_id = models.BigIntegerField(null=True, blank=True)
    corporation_name = models.CharField(
        max_length=128, blank=True, db_index=True
    )
    tribe_names = models.JSONField(default=list, blank=True)
    prime_time = models.CharField(max_length=16, blank=True, db_index=True)
    tenure_days = models.IntegerField(null=True, blank=True)
    tenure_cohort = models.CharField(max_length=16, blank=True, db_index=True)
    activity_tier = models.CharField(max_length=16, blank=True, db_index=True)
    role_flags = models.JSONField(default=list, blank=True)

    # Full autofill block (including any local corrections the member made).
    context_snapshot = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-submitted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "user"],
                name="unique_response_per_user_campaign",
            )
        ]

    def __str__(self):
        return f"{self.user} → {self.campaign_id}"
