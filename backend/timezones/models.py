from django.contrib.auth.models import Group, User
from django.db import models

from timezones.brackets import BRACKETS, REGIONS
from timezones.inference import ACTIVITY, DECLARED

REGION_CHOICES = [(region, region) for region in REGIONS]


class PilotTimezone(models.Model):
    """A pilot's timezones: the one place to read them from.

    ``home`` and ``brackets`` are the answer. ``declared_*`` and
    ``inferred_*`` are the two inputs, kept so callers and admins can see why.
    Written only by timezones.services; read through timezones.services.
    """

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="pilot_timezone"
    )

    # What the pilot said (EvePlayer.prime_time when last assessed).
    declared_prime_time = models.CharField(
        max_length=16, null=True, blank=True
    )
    declared_home = models.CharField(
        max_length=2, null=True, blank=True, choices=REGION_CHOICES
    )

    # What their activity says.
    inferred_home = models.CharField(
        max_length=2, null=True, blank=True, choices=REGION_CHOICES
    )
    inferred_confidence = models.FloatField(
        null=True,
        blank=True,
        help_text="The home model's P(home); empty for AU or no activity.",
    )

    # The answer.
    home = models.CharField(
        max_length=2, null=True, blank=True, choices=REGION_CHOICES
    )
    home_source = models.CharField(
        max_length=16,
        null=True,
        blank=True,
        choices=[(ACTIVITY, "Activity"), (DECLARED, "Declared")],
    )
    brackets = models.JSONField(
        default=list, help_text='Bracket codes, e.g. ["USTZ", "EUTZ"].'
    )

    # Evidence.
    evenings = models.JSONField(
        default=dict,
        help_text="Distinct evenings per region prime/late window.",
    )
    active_days = models.IntegerField(default=0)
    events = models.IntegerField(default=0)

    # Whether the pilot should hold Discord roles for their brackets:
    # an active or trial member with Discord linked.
    eligible = models.BooleanField(default=False)

    assessed_at = models.DateTimeField()
    changed_at = models.DateTimeField(
        help_text="When home or brackets last changed."
    )

    class Meta:
        indexes = [models.Index(fields=["eligible", "home"])]

    def __str__(self):
        return f"{self.user} {self.home or '-'} {' '.join(self.brackets)}"


class TimezoneRole(models.Model):
    """The auth group (and so the Discord role) for one bracket."""

    code = models.CharField(
        max_length=16,
        unique=True,
        choices=[(bracket.code, bracket.code) for bracket in BRACKETS],
    )
    group = models.OneToOneField(
        Group, on_delete=models.CASCADE, related_name="timezone_role"
    )

    def __str__(self):
        return str(self.code)
