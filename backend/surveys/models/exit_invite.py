from django.contrib.auth.models import User
from django.db import models

CHANNEL_EVE_MAIL = "eve_mail"
CHANNEL_DISCORD_DM = "discord_dm"
STATUS_SENT = "sent"
STATUS_NOT_DELIVERED = "not_delivered"


class ExitSurveyInvite(models.Model):
    """The one exit or alliance move survey a person gets (#3198).

    Read only by the Alliance Executor: no API but the token endpoints, and
    admin pages for the Executor's account only.
    """

    CHANNEL_CHOICES = (
        ("", "None"),
        (CHANNEL_EVE_MAIL, "Eve mail"),
        (CHANNEL_DISCORD_DM, "Discord DM"),
    )
    STATUS_CHOICES = (
        (STATUS_SENT, "Sent"),
        (STATUS_NOT_DELIVERED, "Not delivered"),
    )

    departure = models.OneToOneField(
        "exits.Departure",
        on_delete=models.CASCADE,
        related_name="survey_invite",
    )
    character_id = models.BigIntegerField(db_index=True)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    definition_key = models.CharField(max_length=32)
    definition_version = models.PositiveIntegerField()
    channel = models.CharField(
        max_length=16, choices=CHANNEL_CHOICES, default="", blank=True
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES)
    sent_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    responded_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.definition_key} survey for {self.character_id} ({self.status})"
