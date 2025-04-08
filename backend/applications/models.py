from django.contrib.auth.models import User
from django.db import models

from eveonline.models import EveCorporation
from eveonline.helpers.characters import user_primary_character


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
    corporation = models.ForeignKey(EveCorporation, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="processed_by",
        blank=True,
        null=True,
    )
    discord_thread_id = models.BigIntegerField(blank=True, null=True)

    def __str__(self):
        primary_character = user_primary_character(self.user)
        if primary_character:
            return f"{primary_character.character_name}'s application to {self.corporation.name}"
        return f"{self.user}'s application to {self.corporation.name}"
