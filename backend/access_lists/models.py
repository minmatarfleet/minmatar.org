from django.db import models

from eveonline.models import EveCharacter


class AccessLevel(models.TextChoices):
    BLOCKED = "Blocked", "Blocked"
    ALLOWED = "Allowed", "Allowed"
    MANAGER = "Manager", "Manager"
    ADMIN = "Admin", "Admin"


class EntityType(models.TextChoices):
    CHARACTER = "character", "Character"
    CORPORATION = "corporation", "Corporation"
    ALLIANCE = "alliance", "Alliance"


class EveAccessList(models.Model):
    """An in-game access list managed by an executor character."""

    access_list_id = models.PositiveBigIntegerField(
        primary_key=True,
        verbose_name="Access list ID",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    allow_everyone = models.BooleanField(default=False)
    owner_character = models.ForeignKey(
        EveCharacter,
        on_delete=models.CASCADE,
        related_name="access_lists",
    )
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Access list"
        verbose_name_plural = "Access lists"
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["owner_character"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.access_list_id})"


class EveAccessListMember(models.Model):
    """A character, corporation, or alliance entry on an access list."""

    access_list = models.ForeignKey(
        EveAccessList,
        on_delete=models.CASCADE,
        related_name="members",
    )
    entity_type = models.CharField(max_length=20, choices=EntityType.choices)
    entity_id = models.BigIntegerField()
    entity_name = models.CharField(max_length=255, blank=True)
    access = models.CharField(max_length=20, choices=AccessLevel.choices)

    class Meta:
        verbose_name = "Access list member"
        verbose_name_plural = "Access list members"
        constraints = [
            models.UniqueConstraint(
                fields=["access_list", "entity_type", "entity_id"],
                name="access_lists_unique_member",
            )
        ]
        indexes = [
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["access"]),
        ]

    def __str__(self):
        label = self.entity_name or str(self.entity_id)
        return f"{label} ({self.access})"
