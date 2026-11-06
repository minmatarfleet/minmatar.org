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


class CorporationRequirement(models.Model):
    """One recruitment rule a corporation asks of applicants.

    The site checks it against the applicant's characters. Required rules
    gate the apply button; preferred rules only show. The corp's free-text
    ``EveCorporation.requirements`` lines stay as interview topics, so a
    corp with no rules here keeps working exactly as before.
    Params per kind are validated in applications.requirements.rules.
    """

    KIND_SHIPS = "ships"
    KIND_KILLS = "kills"
    KIND_SKILL_POINTS = "skill_points"
    KIND_CHARACTER_AGE = "character_age"
    KIND_PRIME_TIME = "prime_time"
    KIND_CHOICES = [
        (KIND_SHIPS, "Fly a doctrine or role"),
        (KIND_KILLS, "Kills over time"),
        (KIND_SKILL_POINTS, "Skill points"),
        (KIND_CHARACTER_AGE, "Character age"),
        (KIND_PRIME_TIME, "Plays in our prime time"),
    ]

    WHO_MAIN = "main"
    WHO_ANY = "any"
    WHO_OTHER_ACCOUNT = "other_account"
    WHO_CHOICES = [
        (WHO_MAIN, "Main"),
        (WHO_ANY, "Any character"),
        (WHO_OTHER_ACCOUNT, "An alt on another account"),
    ]

    IMPORTANCE_REQUIRED = "required"
    IMPORTANCE_PREFERRED = "preferred"
    IMPORTANCE_CHOICES = [
        (IMPORTANCE_REQUIRED, "Required"),
        (IMPORTANCE_PREFERRED, "Preferred"),
    ]

    corporation = models.ForeignKey(
        EveCorporation,
        on_delete=models.CASCADE,
        related_name="recruitment_requirements",
    )
    kind = models.CharField(max_length=32, choices=KIND_CHOICES)
    params = models.JSONField(default=dict, blank=True)
    who = models.CharField(max_length=16, choices=WHO_CHOICES, default=WHO_ANY)
    importance = models.CharField(
        max_length=16,
        choices=IMPORTANCE_CHOICES,
        default=IMPORTANCE_PREFERRED,
    )
    position = models.IntegerField(default=0)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["corporation", "position", "id"]

    def __str__(self):
        return f"{self.corporation.name}: {self.kind} ({self.importance})"
