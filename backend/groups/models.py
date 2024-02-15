from django.db import models
from eveuniverse.models import EveFaction

from eveonline.models import EveAlliance, EveCorporation


# Create your models here.
class RequestableGroup(models.Model):
    """Model for groups that users can request to join."""

    name = models.CharField(max_length=64)
    description = models.TextField(null=True, blank=True)
    image_url = models.URLField(null=True, blank=True)
    required_groups = models.ManyToManyField(
        "auth.Group", related_name="required_by", blank=True
    )
    group_managers = models.ManyToManyField(
        "auth.User", related_name="managed_groups"
    )
    group = models.OneToOneField("auth.Group", on_delete=models.CASCADE)

    def __str__(self):
        return self.group.name


class AutoGroup(models.Model):
    """Automatically assigned groups based on corporation, alliance or faction membership."""

    name = models.CharField(max_length=64)
    description = models.TextField(null=True, blank=True)
    image_url = models.URLField(null=True, blank=True)
    group = models.OneToOneField("auth.Group", on_delete=models.CASCADE)
    priority = models.IntegerField(unique=True)
    corporations = models.ManyToManyField(EveCorporation)
    alliances = models.ManyToManyField(EveAlliance)
    factions = models.ManyToManyField(EveFaction)

    def __str__(self):
        return self.group.name


class GroupRequest(models.Model):
    """Model for a user request to join a group"""

    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    group = models.ForeignKey("auth.Group", on_delete=models.CASCADE)
    approved = models.BooleanField(null=True, blank=True, default=None)
    approved_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_requests",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user} - {self.group}"
