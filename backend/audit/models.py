from django.db import models

from django.contrib.auth.models import User
from eveonline.models import EveCharacter


class AuditEntry(models.Model):
    """An auditable event"""

    category_choices = (
        ("user_registered", "User registered"),
        ("user_deleted", "User deleteed"),
        ("primary_char", "Primary character set"),
        ("character_added", "Character added"),
        ("character_deleted", "Character deleted"),
        ("team_change", "Team changed"),
        ("other", "Other"),
    )
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    character = models.ForeignKey(
        EveCharacter, on_delete=models.SET_NULL, null=True
    )
    old_character_id = models.BigIntegerField(null=True, blank=True)

    category = models.CharField(
        max_length=32, choices=category_choices, null=False, db_index=True
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    summary = models.CharField(max_length=255)
