import uuid

from django.contrib.auth.models import User
from django.db import models


class OnboardingProgramType(models.TextChoices):
    """Hardcoded onboarding programs; add new values here and deploy."""

    SRP = "srp", "SRP"


class OnboardingProgram(models.Model):
    program_type = models.CharField(
        max_length=32,
        primary_key=True,
        choices=OnboardingProgramType.choices,
    )
    version = models.UUIDField(default=uuid.uuid4)

    def __str__(self):
        return self.program_type


class UserOnboardingAcknowledgment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    program = models.ForeignKey(
        OnboardingProgram,
        on_delete=models.CASCADE,
        related_name="acknowledgments",
    )
    acknowledged_version = models.UUIDField()
    acknowledged_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("user", "program"),)
