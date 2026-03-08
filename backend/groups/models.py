from django.db import models
from eveuniverse.models import EveFaction

from eveonline.models import EveAlliance, EveCorporation

# Create your models here.


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
    requires_trial = models.BooleanField(
        default=False,
        help_text="When True, users who first get this affiliation start as trial.",
    )

    def __str__(self):
        return self.group.name


class UserCommunityStatus(models.Model):
    """Current community status for a user (trial, active, on_leave). Overrides effective group."""

    STATUS_ACTIVE = "active"
    STATUS_TRIAL = "trial"
    STATUS_ON_LEAVE = "on_leave"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_TRIAL, "Trial"),
        (STATUS_ON_LEAVE, "On Leave"),
    ]

    user = models.OneToOneField(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="community_status",
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
    )

    class Meta:
        verbose_name_plural = "User community statuses"

    def __str__(self):
        return f"{self.user} — {self.get_status_display()}"


class UserCommunityStatusHistory(models.Model):
    """Append-only audit log for community status changes."""

    STATUS_ACTIVE = "active"
    STATUS_TRIAL = "trial"
    STATUS_ON_LEAVE = "on_leave"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_TRIAL, "Trial"),
        (STATUS_ON_LEAVE, "On Leave"),
    ]

    user = models.ForeignKey(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="community_status_history",
    )
    from_status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        null=True,
        blank=True,
    )
    to_status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    changed_by = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="community_status_changes_made",
    )
    reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-changed_at"]
        verbose_name_plural = "User community status histories"

    def __str__(self):
        return f"{self.user} {self.from_status or '?'} → {self.to_status} at {self.changed_at}"


class UserAffiliation(models.Model):
    """One to one relationship table between Affiliation and User"""

    affiliation = models.ForeignKey(AffiliationType, on_delete=models.CASCADE)
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)

    class Meta:
        unique_together = ("affiliation", "user")

    def __str__(self):
        return f"{self.user} - {self.affiliation}"


class EveCorporationGroup(models.Model):
    """Represents a Discord group corresponding to an EveCorporation."""

    GROUP_TYPE_MEMBER = "member"
    GROUP_TYPE_RECRUITER = "recruiter"
    GROUP_TYPE_DIRECTOR = "director"
    GROUP_TYPE_GUNNER = "gunner"
    GROUP_TYPE_CHOICES = [
        (GROUP_TYPE_MEMBER, "Member"),
        (GROUP_TYPE_RECRUITER, "Recruiter"),
        (GROUP_TYPE_DIRECTOR, "Director"),
        (GROUP_TYPE_GUNNER, "Gunner"),
    ]

    # group is the Django authorization group that corresponds to this entity
    group = models.OneToOneField("auth.Group", on_delete=models.CASCADE)

    corporation = models.ForeignKey(EveCorporation, on_delete=models.CASCADE)

    # When set, this is one of the generated role groups (member/recruiter/director/gunner).
    # Null for legacy single group per corporation (treated as member).
    group_type = models.CharField(
        max_length=20,
        choices=GROUP_TYPE_CHOICES,
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("corporation", "group_type"),
                name="groups_evecorporationgroup_corporation_group_type_uniq",
            )
        ]

    def __str__(self):
        return str(self.group.name)
