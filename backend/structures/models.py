from django.contrib.auth.models import User
from django.db import models

from app.models import MinmatarSoftDeleteModel
from eveonline.models import EveCorporation, EveCharacter
from safedelete.config import SOFT_DELETE


class EveStructure(MinmatarSoftDeleteModel):
    """
    Object for tracking structures
    """

    structure_states = (
        ("anchoring", "Anchoring"),
        ("armor_reinforce", "Armor Reinforce"),
        ("armor_vulnerable", "Armor Vulnerable"),
        ("deploy_vulnerable", "Deploy Vulnerable"),
        ("fitting_invulnerable", "Fitting Invulnerable"),
        ("hull_reinforce", "Hull Reinforce"),
        ("hull_vulnerable", "Hull Vulnerable"),
        ("online_deprecated", "Online Deprecated"),
        ("onlining_vulnerable", "Onlining Vulnerable"),
        ("shield_vulnerable", "Shield Vulnerable"),
        ("unanchored", "Unanchored"),
        ("unknown", "Unknown"),
    )
    id = models.BigIntegerField(primary_key=True)
    system_id = models.BigIntegerField()
    system_name = models.CharField(max_length=255)
    type_id = models.BigIntegerField()
    type_name = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    reinforce_hour = models.IntegerField(null=True, blank=True)
    fuel_expires = models.DateTimeField(null=True, blank=True)
    state = models.CharField(
        max_length=255, choices=structure_states, default="unknown"
    )
    state_timer_start = models.DateTimeField(null=True, blank=True)
    state_timer_end = models.DateTimeField(null=True, blank=True)
    fitting = models.TextField(blank=True, null=True)
    is_valid_staging = models.BooleanField(default=False)

    # Null for a reported structure whose owner is not a corporation we
    # track; owner_corporation_name then holds what the reporter typed.
    corporation = models.ForeignKey(
        EveCorporation,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    # Who can see it (universe.access): ESI rows start private, reported
    # rows are always alliance-wide.
    VISIBILITY_ALLIANCE = "alliance"
    VISIBILITY_CORPORATION = "corporation"
    VISIBILITY_PRIVATE = "private"
    VISIBILITY_CHOICES = (
        (VISIBILITY_ALLIANCE, "Alliance"),
        (VISIBILITY_CORPORATION, "Corporation"),
        (VISIBILITY_PRIVATE, "Private"),
    )
    visibility = models.CharField(
        max_length=16, choices=VISIBILITY_CHOICES, default=VISIBILITY_PRIVATE
    )

    SOURCE_ESI = "esi"
    SOURCE_REPORTED = "reported"
    SOURCE_CHOICES = ((SOURCE_ESI, "ESI"), (SOURCE_REPORTED, "Reported"))
    source = models.CharField(
        max_length=16, choices=SOURCE_CHOICES, default=SOURCE_ESI
    )

    owner_corporation_name = models.CharField(
        max_length=255, blank=True, default=""
    )
    owner_alliance_name = models.CharField(
        max_length=255, blank=True, default=""
    )
    affiliated_alliance_name = models.CharField(
        max_length=255, blank=True, default=""
    )

    reported_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reported_structures",
    )
    reported_at = models.DateTimeField(null=True, blank=True)
    last_confirmed_at = models.DateTimeField(null=True, blank=True)
    last_confirmed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="confirmed_structures",
    )
    # A report that may describe a structure the reporter could not see.
    # Admins merge these by hand in Django admin.
    possible_duplicate = models.BooleanField(default=False)

    # Reported rows have no ESI id. They take ids from this far-negative
    # range, clear of the negative ids structure pings use for orbitals.
    REPORTED_ID_BASE = -1_000_000_000_000_000

    @property
    def esi_structure_id(self):
        return self.id if self.id and self.id > 0 else None

    @property
    def owner_name(self) -> str:
        if self.corporation_id:
            return self.corporation.name
        return self.owner_corporation_name

    def delete(self, force_policy=None, **kwargs):
        policy = (
            self._safedelete_policy if force_policy is None else force_policy
        )
        if policy == SOFT_DELETE:
            self.is_valid_staging = False
        return super().delete(force_policy=force_policy, **kwargs)

    def __str__(self):
        return str(f"{self.owner_name or 'Unknown'} - {self.name}")


class EveStructureTimer(models.Model):
    """
    Object for tracking structure timers
    """

    state_choices = (
        ("anchoring", "Anchoring"),
        ("armor", "Armor"),
        ("hull", "Hull"),
        ("unanchoring", "Unanchoring"),
    )

    type_choices = (
        ("astrahus", "Astrahus"),
        ("fortizar", "Fortizar"),
        ("keepstar", "Keepstar"),
        ("raitaru", "Raitaru"),
        ("azbel", "Azbel"),
        ("sotiyo", "Sotiyo"),
        ("athanor", "Athanor"),
        ("tatara", "Tatara"),
        ("tenebrex_cyno_jammer", "Tenebrex Cyno Jammer"),
        ("pharolux_cyno_beacon", "Pharolux Cyno Beacon"),
        ("ansiblex_jump_gate", "Ansiblex Jump Gate"),
        ("orbital_skyhook", "Orbital Skyhook"),
        ("metenox_moon_drill", "Metenox Moon Drill"),
        ("player_owned_customs_office", "Player Owned Customs Office"),
        ("player_owned_starbase", "Player Owned Starbase"),
        ("mercenary_den", "Mercenary Den"),
    )

    name = models.CharField(max_length=255)
    state = models.CharField(max_length=255, choices=state_choices)
    type = models.CharField(max_length=255, choices=type_choices)
    timer = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="structures_created_by",
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="structures_updated_by",
    )

    system_name = models.CharField(max_length=255)
    corporation_name = models.CharField(max_length=255, null=True, blank=True)
    alliance_name = models.CharField(max_length=255, null=True, blank=True)
    fitting = models.TextField(blank=True, null=True)

    structure = models.ForeignKey(
        EveStructure, on_delete=models.SET_NULL, null=True
    )
    campaign = models.ForeignKey(
        "campaigns.Campaign",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="structure_timers",
    )

    def __str__(self):
        if self.structure:
            return str(f"{self.structure.name} - {self.state}")
        else:
            return "Timer without structure"


class EveStructurePing(models.Model):
    """Record of a structure ping"""

    notification_id = models.BigIntegerField(db_index=True)
    notification_type = models.CharField(max_length=40)
    summary = models.CharField(max_length=255)
    discord_success = models.BooleanField(default=False)
    structure_id = models.BigIntegerField(db_index=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    reported_by = models.ForeignKey(
        EveCharacter,
        on_delete=models.SET_NULL,
        null=True,
    )
    text = models.CharField(max_length=2000, null=True)
    event_time = models.DateTimeField(null=True)


class LocationAudienceGroup(models.Model):
    """A tribe group or corporation that can see a location.

    Only used when EveLocation.audience is "groups".
    """

    location = models.ForeignKey(
        "eveonline.EveLocation",
        on_delete=models.CASCADE,
        related_name="audience_groups",
    )
    tribe_group = models.ForeignKey(
        "tribes.TribeGroup",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="+",
    )
    corporation = models.ForeignKey(
        EveCorporation,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="+",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(tribe_group__isnull=False)
                | models.Q(corporation__isnull=False),
                name="location_audience_has_target",
            )
        ]


class LocationSubmission(models.Model):
    """A structure a pilot asked to add. A manager approves it into an
    EveLocation. Submissions without a structure ID stay pending until one
    turns up (location_id is EveLocation's primary key)."""

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_DECLINED = "declined"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_DECLINED, "Declined"),
    )

    location_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    id_source = models.CharField(
        max_length=16,
        blank=True,
        default="",
        help_text="How the ID was found: search, docked, structure, listed.",
    )
    name = models.CharField(max_length=255)
    short_name = models.CharField(max_length=32, blank=True, default="")
    type_id = models.IntegerField(null=True, blank=True)
    solar_system_id = models.BigIntegerField(null=True, blank=True)
    solar_system_name = models.CharField(
        max_length=255, blank=True, default=""
    )
    paste_text = models.TextField(blank=True, default="")
    fitting = models.JSONField(default=list, blank=True)
    reinforce_hour = models.PositiveSmallIntegerField(null=True, blank=True)
    audience = models.CharField(max_length=16, default="alliance")
    audience_tribe_group_ids = models.JSONField(default=list, blank=True)
    good_for = models.JSONField(default=list, blank=True)
    description = models.TextField(blank=True, default="")

    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    submitted_by = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    decided_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decline_reason = models.CharField(max_length=255, blank=True, default="")

    def __str__(self):
        return f"{self.name} ({self.status})"


class LocationChange(models.Model):
    """One entry on a location's History tab."""

    KIND_CHOICES = (
        ("added", "Added"),
        ("approved", "Approved"),
        ("fitting", "Fitting"),
        ("details", "Details"),
        ("audience", "Audience"),
        ("flags", "Site settings"),
        ("retired", "Retired"),
        ("restored", "Added back"),
    )

    location = models.ForeignKey(
        "eveonline.EveLocation",
        on_delete=models.CASCADE,
        related_name="changes",
    )
    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    kind = models.CharField(max_length=16, choices=KIND_CHOICES)
    summary = models.CharField(max_length=255)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
