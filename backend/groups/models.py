from django.db import models
from eveuniverse.models import EveFaction

from eveonline.models import EveAlliance, EveCorporation

# Create your models here.


class Team(models.Model):
    """Model for teams that users can join."""

    name = models.CharField(max_length=64)
    description = models.TextField(null=True, blank=True)
    image_url = models.URLField(null=True, blank=True)
    directors = models.ManyToManyField("auth.User", related_name="director_of")
    members = models.ManyToManyField("auth.User", related_name="teams")
    group = models.OneToOneField("auth.Group", on_delete=models.CASCADE)

    def __str__(self):
        return self.group.name


class TeamRequest(models.Model):
    """Model for a user request to join a team"""

    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    approved = models.BooleanField(null=True, blank=True, default=None)
    approved_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_team_requests",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user} - {self.team}"


class Sig(models.Model):
    """Model for special interest groups that users can join."""

    name = models.CharField(max_length=64)
    description = models.TextField(null=True, blank=True)
    image_url = models.URLField(null=True, blank=True)
    officers = models.ManyToManyField("auth.User", related_name="officer_of")
    members = models.ManyToManyField("auth.User", related_name="sigs")
    group = models.OneToOneField("auth.Group", on_delete=models.CASCADE)

    def __str__(self):
        return self.group.name


class SigRequest(models.Model):
    """Model for a user request to join"""

    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    sig = models.ForeignKey(Sig, on_delete=models.CASCADE)
    approved = models.BooleanField(null=True, blank=True, default=None)
    approved_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_sig_requests",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user} - {self.sig}"


class AffiliationType(models.Model):
    """Automatically assigned groups based on corporation, alliance or faction membership."""

    name = models.CharField(max_length=64)
    description = models.TextField(null=True, blank=True)
    image_url = models.URLField(null=True, blank=True)
    group = models.OneToOneField("auth.Group", on_delete=models.CASCADE)
    priority = models.IntegerField(unique=True)
    corporations = models.ManyToManyField(EveCorporation, blank=True)
    alliances = models.ManyToManyField(EveAlliance, blank=True)
    factions = models.ManyToManyField(EveFaction, blank=True)
    default = models.BooleanField(default=False)

    def __str__(self):
        return self.group.name


class UserAffiliation(models.Model):
    """One to one relationship table between Affiliation and User"""

    affiliation = models.ForeignKey(AffiliationType, on_delete=models.CASCADE)
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)

    class Meta:
        unique_together = ("affiliation", "user")

    def __str__(self):
        return f"{self.user} - {self.affiliation}"
