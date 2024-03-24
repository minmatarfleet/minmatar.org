from django.contrib.auth.models import User
from django.db import models

from eveonline.models import EveCorporation, EvePrimaryCharacter


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
        if EvePrimaryCharacter.objects.filter(
            character__token__user=self.user
        ).exists():
            primary_character = EvePrimaryCharacter.objects.get(
                character__token__user=self.user
            )
            return f"{primary_character.character.character_name}'s application to {self.corporation.name}"
        return f"{self.user}'s application to {self.corporation.name}"
