from django.contrib.auth.models import User
from django.db import models

from eveonline.helpers.characters import user_primary_character
from eveonline.models import EveCorporation


# Create your models here.
class EveCorporationApplication(models.Model):
    """Corporation application model"""

    status_choices = (
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
    )
    status = models.CharField(
        max_length=10, choices=status_choices, default="pending"
    )
    description = models.TextField(blank=True)
    corporation_id = models.BigIntegerField()
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="processed_by",
        blank=True,
        null=True,
    )
    discord_thread_id = models.BigIntegerField(blank=True, null=True)

    def __str__(self):
        primary_character = user_primary_character(self.user)
        corp_name = corporation_name_for_application(self)
        if primary_character:
            return f"{primary_character.character_name}'s application to {corp_name}"
        return f"{self.user}'s application to {corp_name}"


def open_application_for_user(user):
    """The applicant's pending corporation application, if they have one."""
    return (
        EveCorporationApplication.objects.filter(user=user, status="pending")
        .order_by("-created_at", "-id")
        .first()
    )


def corporation_name_for_application(application) -> str:
    corporation = EveCorporation.objects.filter(
        corporation_id=application.corporation_id
    ).first()
    return corporation.name if corporation else str(application.corporation_id)


def open_application_detail(application) -> str:
    name = corporation_name_for_application(application)
    return (
        f"You already have an open application to {name}. "
        "Wait for a decision before applying again."
    )
