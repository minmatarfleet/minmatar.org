"""Data model for live, multi-system Faction Warfare campaigns.

A campaign is a named operation over a handful of warzone systems that runs
for a month or two. Everything an enlisted pilot does inside those systems is
counted: kills, losses, complex captures, advantage sites, fleets. See
``docs/campaigns/fw-campaigns-plan.md`` for the product specification.
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from campaigns.constants import (
    ADVANTAGE_DELTA_BY_SITE_KIND,
    CAMPAIGN_COVER_CHOICES,
)

# The campaign week and campaign day both roll over at 11:00 UTC, which is
# shortly after EVE's daily downtime and the moment FW victory points reset.
DAY_BOUNDARY_HOUR = 11


class CampaignStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SCHEDULED = "scheduled", "Scheduled"
    ACTIVE = "active", "Active"
    COMPLETED = "completed", "Completed"
    ARCHIVED = "archived", "Archived"


class CampaignKind(models.TextChoices):
    """How the campaign page reads. Theaters (systems, structures) are separate."""

    FACTION_WARFARE = "faction_warfare", "Faction Warfare"
    STRATEGIC = "strategic", "Strategic"


class StructureStatus(models.TextChoices):
    ANCHORED = "anchored", "Anchored"
    REINFORCED = "reinforced", "Reinforced"
    DESTROYED = "destroyed", "Destroyed"
    UNANCHORED = "unanchored", "Unanchored"


class StructureSource(models.TextChoices):
    RECON = "recon", "Recon"
    TIMER = "timer", "Timer"
    KILLMAIL = "killmail", "Killmail"


class SystemGoal(models.TextChoices):
    TAKE = "take", "Take"
    HOLD = "hold", "Hold"
    PRESSURE = "pressure", "Pressure"
    DISRUPT = "disrupt", "Disrupt"
    RECON = "recon", "Recon"
    NONE = "none", "No goal"


class SystemRole(models.TextChoices):
    PRIMARY = "primary", "Primary"
    SECONDARY = "secondary", "Secondary"
    SUPPORT = "support", "Support"


class SystemPriority(models.TextChoices):
    """How urgently a system needs people; orders the boards."""

    HIGH = "high", "High"
    MEDIUM = "medium", "Medium"
    LOW = "low", "Low"


class AreaScope(models.TextChoices):
    """Constellation or region included as an ops theater (never FW)."""

    CONSTELLATION = "constellation", "Constellation"
    REGION = "region", "Region"


class SiteKind(models.TextChoices):
    COMPLEX = "complex", "Complex"
    ADVANTAGE_SITE = "advantage_site", "Advantage site"
    RENDEZVOUS_POINT = "rendezvous_point", "Rendezvous Point"
    PROPAGANDA_BEACON = "propaganda_beacon", "Propaganda Beacon"
    LISTENING_OUTPOST = "listening_outpost", "Listening Outpost"
    SUPPLY_CACHE = "supply_cache", "Supply Cache"
    BATTLEFIELD = "battlefield", "Battlefield"
    KILL = "kill", "Kill payout"
    UNKNOWN = "unknown", "Unknown"


class KillmailOutcome(models.TextChoices):
    KILL = "kill", "Kill"
    LOSS = "loss", "Loss"
    AWOX = "awox", "Awox"
    UNSCORED = "unscored", "Unscored"


class OperationalState(models.TextChoices):
    FRONTLINE = "frontline", "Frontline"
    COMMAND = "command_operations", "Command Operations"
    REARGUARD = "rearguard", "Rearguard"
    UNKNOWN = "unknown", "Unknown"


class Campaign(models.Model):
    """One named operation. Theaters may be systems, structures, or both."""

    slug = models.SlugField(max_length=64, unique=True)
    short_code = models.CharField(
        max_length=12,
        unique=True,
        help_text="Donation tag, e.g. BLP. Used to match wallet journal "
        "entries and content tags to this campaign.",
    )
    name = models.CharField(max_length=128)
    tagline = models.CharField(max_length=200, blank=True, default="")
    description_md = models.TextField(blank=True, default="")
    cover_image_url = models.CharField(
        max_length=512,
        blank=True,
        default="",
        choices=CAMPAIGN_COVER_CHOICES,
        help_text="Pick from the site cover gallery. Leave default to use "
        "the kind fallback on the campaign card.",
    )

    kind = models.CharField(
        max_length=24,
        choices=CampaignKind.choices,
        default=CampaignKind.FACTION_WARFARE,
        db_index=True,
        help_text="Display preset. Does not change how activity is matched.",
    )
    status = models.CharField(
        max_length=16,
        choices=CampaignStatus.choices,
        default=CampaignStatus.DRAFT,
        db_index=True,
    )
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    visibility = models.CharField(
        max_length=16,
        choices=(("alliance", "Alliance"), ("public", "Public")),
        default="alliance",
    )

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    discord_channel_id = models.BigIntegerField(null=True, blank=True)
    voice_channel_ids = models.JSONField(default=list, blank=True)
    default_fleet_audience = models.ForeignKey(
        "fleets.EveFleetAudience",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    scoring = models.JSONField(
        default=dict,
        blank=True,
        help_text="Overrides for the default scoring weights.",
    )
    order_pool = models.JSONField(default=dict, blank=True)

    commander_order_text = models.CharField(
        max_length=280, blank=True, default=""
    )
    commander_order_set_at = models.DateTimeField(null=True, blank=True)
    commander_order_is_draft = models.BooleanField(default=True)

    donation_corporation_id = models.BigIntegerField(null=True, blank=True)
    donation_division = models.PositiveSmallIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_at"]
        indexes = [models.Index(fields=["status", "-start_at"])]

    def __str__(self) -> str:
        return str(self.name)

    @property
    def is_live(self) -> bool:
        return self.status == CampaignStatus.ACTIVE

    @property
    def is_counting(self) -> bool:
        """Scheduled campaigns already attribute, so nothing is missed."""
        return self.status in (
            CampaignStatus.SCHEDULED,
            CampaignStatus.ACTIVE,
        )

    def system_ids(self) -> list[int]:
        return list(
            self.systems.filter(retired_at__isnull=True).values_list(
                "solar_system_id", flat=True
            )
        )

    @property
    def is_faction_warfare(self) -> bool:
        return self.kind == CampaignKind.FACTION_WARFARE

    @property
    def is_strategic(self) -> bool:
        return self.kind == CampaignKind.STRATEGIC


class PartyKind(models.TextChoices):
    CHARACTER = "character", "Character"
    CORPORATION = "corporation", "Corporation"
    ALLIANCE = "alliance", "Alliance"
    FACTION = "faction", "Faction"


class PartySide(models.TextChoices):
    ENEMY = "enemy", "Enemy"
    ALLY = "ally", "Ally"


class StructureAffiliation(models.TextChoices):
    HOSTILE = "hostile", "Hostile"
    FRIENDLY = "friendly", "Friendly"
    NEUTRAL = "neutral", "Neutral"


class CampaignParty(models.Model):
    """A character, corp, alliance, or faction on our side or theirs."""

    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="parties"
    )
    kind = models.CharField(
        max_length=16,
        choices=PartyKind.choices,
        default=PartyKind.ALLIANCE,
        db_index=True,
    )
    side = models.CharField(
        max_length=8,
        choices=PartySide.choices,
        default=PartySide.ENEMY,
        db_index=True,
    )
    character_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    corporation_id = models.BigIntegerField(
        null=True, blank=True, db_index=True
    )
    alliance_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    faction_id = models.IntegerField(null=True, blank=True, db_index=True)
    name = models.CharField(max_length=255)
    ticker = models.CharField(max_length=16, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["side", "name"]
        verbose_name_plural = "parties"
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "alliance_id"],
                name="campaign_party_alliance_unique",
                condition=models.Q(alliance_id__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["campaign", "corporation_id"],
                name="campaign_party_corporation_unique",
                condition=models.Q(corporation_id__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["campaign", "character_id"],
                name="campaign_party_character_unique",
                condition=models.Q(character_id__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["campaign", "faction_id"],
                name="campaign_party_faction_unique",
                condition=models.Q(faction_id__isnull=False),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.side}, {self.campaign.slug})"

    @property
    def entity_id(self) -> int | None:
        if self.kind == PartyKind.CHARACTER:
            return self.character_id
        if self.kind == PartyKind.CORPORATION:
            return self.corporation_id
        if self.kind == PartyKind.ALLIANCE:
            return self.alliance_id
        if self.kind == PartyKind.FACTION:
            return self.faction_id
        return None


class CampaignStructure(models.Model):
    """A structure under recon for a campaign: timer, kill, or paste."""

    # Same string keys as EveStructureTimer.type_choices / frontend get_structure_id.
    TYPE_CHOICES = (
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

    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="structures"
    )
    name = models.CharField(max_length=255)
    structure_type = models.CharField(max_length=64, choices=TYPE_CHOICES)
    type_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="ESI type id when known; used to match killmails.",
    )
    solar_system_id = models.BigIntegerField(db_index=True)
    system_name = models.CharField(max_length=128)
    corporation_id = models.BigIntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="ESI corporation id of the structure's legal owner.",
    )
    corporation_name = models.CharField(max_length=255, blank=True, default="")
    alliance_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    alliance_name = models.CharField(max_length=255, blank=True, default="")
    related_alliance_id = models.BigIntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "Affiliated alliance when the legal owner is an alt corp "
            "(e.g. CVA). Used with campaign parties for hostile/friendly."
        ),
    )
    related_alliance_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Scout-entered affiliated alliance name.",
    )
    eve_structure_id = models.BigIntegerField(null=True, blank=True)
    fitting = models.TextField(
        blank=True,
        default="",
        help_text="Scouted structure fit paste (high slots, services, etc.).",
    )
    reinforce_hour = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="EVE reinforce hour (0–23), e.g. 18 for 18:00.",
    )

    status = models.CharField(
        max_length=16,
        choices=StructureStatus.choices,
        default=StructureStatus.ANCHORED,
        db_index=True,
    )
    source = models.CharField(
        max_length=16,
        choices=StructureSource.choices,
        default=StructureSource.RECON,
    )
    timer = models.ForeignKey(
        "structures.EveStructureTimer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campaign_structures",
    )
    destroyed_at = models.DateTimeField(null=True, blank=True)
    killmail = models.ForeignKey(
        "CampaignKillmail",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="destroyed_structures",
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["system_name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "campaign",
                    "solar_system_id",
                    "structure_type",
                    "name",
                ],
                name="campaign_structure_identity_unique",
            )
        ]
        indexes = [
            models.Index(fields=["campaign", "status"]),
            models.Index(fields=["campaign", "solar_system_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.system_name})"


class CampaignSystem(models.Model):
    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="systems"
    )
    # Type-ahead lookup in admin; denormalized ids/name stay for API/scoring.
    eve_solar_system = models.ForeignKey(
        "eveuniverse.EveSolarSystem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    solar_system_id = models.BigIntegerField(db_index=True)
    name = models.CharField(max_length=64)
    region_id = models.BigIntegerField(null=True, blank=True)
    role = models.CharField(
        max_length=16, choices=SystemRole.choices, default=SystemRole.PRIMARY
    )
    priority = models.CharField(
        max_length=8,
        choices=SystemPriority.choices,
        default=SystemPriority.MEDIUM,
    )
    goal = models.CharField(
        max_length=16, choices=SystemGoal.choices, default=SystemGoal.TAKE
    )
    is_fw_objective = models.BooleanField(
        default=True,
        db_index=True,
        help_text=(
            "FW contest objective (plex/VP/advantage). "
            "Off = ops theater only (structure hunt / member guide; no kill scoring)."
        ),
    )
    added_at = models.DateTimeField(default=timezone.now)
    retired_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "solar_system_id"],
                name="campaign_system_unique",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.campaign.slug})"

    def sync_from_eve_solar_system(self) -> None:
        """Copy id/name/region from the autocomplete FK when set."""
        system = self.eve_solar_system
        if system is None:
            return
        self.solar_system_id = int(system.id)
        self.name = system.name or self.name
        if system.eve_constellation_id:
            self.region_id = system.eve_constellation.eve_region_id


class CampaignArea(models.Model):
    """Constellation or region in the campaign as an ops theater.

    Never an FW objective: guidance for members and structure hunting only.
    Does not pull kill attribution.
    """

    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="areas"
    )
    scope = models.CharField(max_length=16, choices=AreaScope.choices)
    constellation_id = models.BigIntegerField(
        null=True, blank=True, db_index=True
    )
    region_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    eve_constellation = models.ForeignKey(
        "eveuniverse.EveConstellation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    eve_region = models.ForeignKey(
        "eveuniverse.EveRegion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    name = models.CharField(max_length=128)
    goal = models.CharField(
        max_length=16,
        choices=SystemGoal.choices,
        default=SystemGoal.RECON,
        help_text="What members should do in this constellation or region.",
    )
    priority = models.CharField(
        max_length=8,
        choices=SystemPriority.choices,
        default=SystemPriority.MEDIUM,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "scope", "constellation_id"],
                condition=models.Q(scope="constellation"),
                name="campaign_area_constellation_unique",
            ),
            models.UniqueConstraint(
                fields=["campaign", "scope", "region_id"],
                condition=models.Q(scope="region"),
                name="campaign_area_region_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.scope}, {self.campaign.slug})"

    def sync_from_eve_lookups(self) -> None:
        """Copy id/name from constellation or region autocomplete FKs."""
        if self.scope == AreaScope.CONSTELLATION and self.eve_constellation_id:
            constellation = self.eve_constellation
            self.constellation_id = int(constellation.id)
            self.name = constellation.name or self.name
            self.region_id = None
            self.eve_region = None
        elif self.scope == AreaScope.REGION and self.eve_region_id:
            region = self.eve_region
            self.region_id = int(region.id)
            self.name = region.name or self.name
            self.constellation_id = None
            self.eve_constellation = None


class CampaignSystemArc(models.Model):
    """The one long-lived goal per system, set once when the campaign starts."""

    campaign_system = models.OneToOneField(
        CampaignSystem, on_delete=models.CASCADE, related_name="arc"
    )
    target_state = models.CharField(
        max_length=8,
        choices=(("flip", "Flip to us"), ("hold", "Hold")),
        default="flip",
    )
    due_at = models.DateTimeField(null=True, blank=True)
    contest_ceiling = models.FloatField(
        default=25.0, help_text="Defend: keep enemy contest under this."
    )
    advantage_floor = models.FloatField(
        default=0.0, help_text="Defend: keep our net advantage above this."
    )

    class AdvantageTask(models.TextChoices):
        NONE = "none", "No advantage task"
        GAIN = "gain", "Gain advantage (build ours up to a level)"
        DESTROY = "destroy", "Destroy advantage (knock theirs down to a level)"
        MAINTAIN = "maintain", "Maintain advantage (keep ours at or above)"

    # Advantage is a separate job from plexing, and it comes in three
    # shapes a pilot can act on. The target is a level on the 0-100 scale
    # the in-game panel shows; each task has a sensible default.
    advantage_task = models.CharField(
        max_length=8,
        choices=AdvantageTask.choices,
        default=AdvantageTask.NONE,
    )
    advantage_target = models.FloatField(null=True, blank=True)
    vp_needed_at_start = models.BigIntegerField(null=True, blank=True)

    DEFAULT_ADVANTAGE_TARGETS = {
        "gain": 75.0,
        "destroy": 50.0,
        "maintain": 90.0,
    }

    @property
    def advantage_level(self) -> float | None:
        """The level the advantage task aims at, defaulted per task."""
        if self.advantage_task == self.AdvantageTask.NONE:
            return None
        if self.advantage_target is not None:
            return self.advantage_target
        return self.DEFAULT_ADVANTAGE_TARGETS[self.advantage_task]

    def __str__(self) -> str:
        return f"Arc for {self.campaign_system}"


class CampaignWeekTarget(models.Model):
    """Auto-proposed weekly target; an operator accepts or nudges it."""

    class Metric(models.TextChoices):
        VICTORY_POINTS = "victory_points", "Victory points"
        DAYS_UNDER_LINE = "days_under_line", "Days under contest line"
        ADVANTAGE = "advantage", "Advantage generated"
        # Levels, not flows: where our (or their) advantage stands on the
        # 0-100 scale against the level the task aims at.
        ADVANTAGE_GAIN = "advantage_gain", "Gain advantage"
        ADVANTAGE_DESTROY = "advantage_destroy", "Destroy advantage"
        ADVANTAGE_MAINTAIN = "advantage_maintain", "Maintain advantage"
        # Strategic / structure campaigns: scout and paste enemy structures.
        STRUCTURES_REPORTED = "structures_reported", "Structures reported"

    ADVANTAGE_METRICS = (
        "advantage_gain",
        "advantage_destroy",
        "advantage_maintain",
    )

    campaign_system = models.ForeignKey(
        CampaignSystem, on_delete=models.CASCADE, related_name="week_targets"
    )
    week_start = models.DateField(db_index=True)
    metric = models.CharField(
        max_length=24,
        choices=Metric.choices,
        default=Metric.VICTORY_POINTS,
    )
    target = models.FloatField(default=0)
    proposed = models.BooleanField(default=True)
    accepted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    accepted_at = models.DateTimeField(null=True, blank=True)

    progress = models.FloatField(default=0)
    pace_expected = models.FloatField(default=0)
    # Where a level metric stood when the week opened; pace ramps from here.
    baseline = models.FloatField(default=0)
    days_under_line = models.PositiveSmallIntegerField(default=0)
    last_week_actual = models.FloatField(default=0)
    projected_arc_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-week_start"]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign_system", "week_start", "metric"],
                name="campaign_week_target_unique",
            )
        ]

    def __str__(self) -> str:
        return f"{self.campaign_system} {self.week_start} {self.metric}"

    @property
    def lower_is_better(self) -> bool:
        return self.metric == self.Metric.ADVANTAGE_DESTROY

    @property
    def pace(self) -> str:
        """on_pace / behind / ahead — never red before the week is done."""
        if self.target <= 0:
            return "on_pace"
        if self.lower_is_better:
            # Knocking a level down: progress is the enemy's level, and
            # the ramp runs from the baseline down to the target.
            want = max(0.0, self.baseline - self.pace_expected)
            done = max(0.0, self.baseline - self.progress)
            if want <= 0:
                return "on_pace" if self.progress <= self.target else "behind"
            ratio = done / want
        else:
            if self.pace_expected <= 0:
                return "on_pace"
            ratio = self.progress / self.pace_expected
        if ratio >= 1.1:
            return "ahead"
        if ratio < 0.8:
            return "behind"
        return "on_pace"


class CampaignSystemInsurgency(models.Model):
    """Manager-set insurgency stage; ESI exposes no endpoint for this."""

    campaign_system = models.ForeignKey(
        CampaignSystem, on_delete=models.CASCADE, related_name="insurgencies"
    )
    suppression_stage = models.PositiveSmallIntegerField(default=0)
    corruption_stage = models.PositiveSmallIntegerField(default=0)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField(null=True, blank=True)
    source = models.CharField(
        max_length=16,
        choices=(("manual", "Manual"), ("inferred", "Inferred")),
        default="manual",
    )
    confirmed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-valid_from"]

    def __str__(self) -> str:
        return f"{self.campaign_system} suppression {self.suppression_stage}"


class CampaignFitting(models.Model):
    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="fittings"
    )
    fitting = models.ForeignKey(
        "fittings.EveFitting", on_delete=models.CASCADE
    )
    role_label = models.CharField(max_length=64, blank=True, default="")
    srp_eligible = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]


class CampaignEnlistment(models.Model):
    class Source(models.TextChoices):
        FLEET_PROMPT = "fleet_prompt", "Fleet prompt"
        GANG_PING = "gang_ping", "Gang ping"
        WEB = "web", "Web"
        ADMIN = "admin", "Admin"

    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="enlistments"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(
        max_length=16,
        choices=(("active", "Active"), ("left", "Left")),
        default="active",
        db_index=True,
    )
    source = models.CharField(
        max_length=16, choices=Source.choices, default=Source.WEB
    )

    notify_gang_forming = models.BooleanField(default=True)
    notify_standing_fleet = models.BooleanField(default=True)
    notify_activity_nearby = models.BooleanField(default=False)
    notify_streak_at_risk = models.BooleanField(default=True)
    notify_fleets = models.BooleanField(default=True)
    notify_thresholds = models.BooleanField(default=True)
    notify_digest = models.BooleanField(default=True)
    digest_hour = models.PositiveSmallIntegerField(default=18)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "user"], name="campaign_enlistment_unique"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} in {self.campaign.slug}"


class CampaignEnlistmentPeriod(models.Model):
    """Pilots leave and come back; attribution respects the periods."""

    enlistment = models.ForeignKey(
        CampaignEnlistment, on_delete=models.CASCADE, related_name="periods"
    )
    enlisted_at = models.DateTimeField(default=timezone.now)
    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-enlisted_at"]


class CampaignEnlistmentCharacter(models.Model):
    """Which of a pilot's characters count, and when they counted."""

    enlistment = models.ForeignKey(
        CampaignEnlistment, on_delete=models.CASCADE, related_name="characters"
    )
    character = models.ForeignKey(
        "eveonline.EveCharacter", on_delete=models.CASCADE
    )
    included_from = models.DateTimeField(default=timezone.now)
    included_until = models.DateTimeField(null=True, blank=True)
    payouts_polled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Drives the polling rotation so every character is read.",
    )

    class Meta:
        ordering = ["character__character_name"]
        indexes = [models.Index(fields=["character", "included_until"])]

    def __str__(self) -> str:
        return f"{self.character.character_name} ({self.enlistment_id})"

    def included_at(self, when) -> bool:
        if when < self.included_from:
            return False
        return self.included_until is None or when < self.included_until


class CampaignDailyOrder(models.Model):
    class Kind(models.TextChoices):
        FLEET = "fleet", "Fly in a campaign fleet"
        STANDING_FLEET = "standing_fleet", "Fly in the standing fleet"
        KILL = "kill", "Get a kill"
        GANG_KILL = "gang_kill", "Kill alongside enlisted pilots"
        GANG = "gang", "Form or join a gang"
        PLEX = "plex", "Capture complexes"
        ADVANTAGE_SITE = "advantage_site", "Run an advantage site"
        SUPPLY_CACHE = "supply_cache", "Kill a supply cache"
        ADVANTAGE_GENERATED = "advantage_generated", "Generate advantage"
        ADVANTAGE_REPORT = "advantage_report", "Report advantage"
        FIRST_KILL = "first_kill", "Get on any mail"
        FIRST_PLEX = "first_plex", "Capture your first complex"
        WEEKLY_ACTIVE = "weekly_active", "Be active five of seven days"

    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="orders"
    )
    day = models.DateField(db_index=True)
    kind = models.CharField(max_length=32, choices=Kind.choices)
    params = models.JSONField(default=dict, blank=True)
    points = models.IntegerField(default=0)
    scope = models.CharField(
        max_length=8,
        choices=(("all", "Everyone"), ("user", "One pilot")),
        default="all",
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, null=True, blank=True
    )
    campaign_system = models.ForeignKey(
        CampaignSystem, on_delete=models.SET_NULL, null=True, blank=True
    )
    gap_share_pct = models.FloatField(
        default=0,
        help_text="How much of this week's remaining gap this order closes.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["campaign", "day"])]

    def __str__(self) -> str:
        return f"{self.kind} {self.day}"


class CampaignOrderProgress(models.Model):
    order = models.ForeignKey(
        CampaignDailyOrder, on_delete=models.CASCADE, related_name="progress"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    progress = models.FloatField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["order", "user"], name="campaign_order_progress_unique"
            )
        ]


class CampaignSystemSnapshot(models.Model):
    """Durable contested/VP reading. The feed's own table purges at 8 days."""

    campaign_system = models.ForeignKey(
        CampaignSystem, on_delete=models.CASCADE, related_name="snapshots"
    )
    captured_at = models.DateTimeField(db_index=True)
    victory_points = models.BigIntegerField(default=0)
    victory_points_threshold = models.BigIntegerField(default=0)
    contested_percent = models.FloatField(default=0)
    occupier_faction_id = models.IntegerField(null=True, blank=True)
    owner_faction_id = models.IntegerField(null=True, blank=True)
    contested_state = models.CharField(max_length=32, blank=True, default="")
    operational_state = models.CharField(
        max_length=24,
        choices=OperationalState.choices,
        default=OperationalState.UNKNOWN,
    )

    class Meta:
        ordering = ["-captured_at"]
        indexes = [
            models.Index(fields=["campaign_system", "-captured_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.campaign_system} {self.contested_percent:.1f}%"


class CampaignAdvantageReading(models.Model):
    """ESI exposes no advantage, so pilots report what they see."""

    campaign_system = models.ForeignKey(
        CampaignSystem,
        on_delete=models.CASCADE,
        related_name="advantage_readings",
    )
    reported_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    reported_at = models.DateTimeField(default=timezone.now, db_index=True)
    our_pct = models.FloatField()
    enemy_pct = models.FloatField()
    source = models.CharField(
        max_length=16,
        choices=(
            ("pilot", "Pilot"),
            ("manager", "Manager"),
            # CCP's frontlines page publishes advantage per system; a
            # reading from there is exact and needs no consensus.
            ("frontlines", "Frontlines"),
        ),
        default="pilot",
    )
    status = models.CharField(
        max_length=8,
        choices=(
            ("accepted", "Accepted"),
            ("held", "Held"),
            ("rejected", "Rejected"),
        ),
        default="accepted",
    )

    class Meta:
        ordering = ["-reported_at"]

    def __str__(self) -> str:
        return f"{self.campaign_system} {self.our_pct}/{self.enemy_pct}"


class CampaignAdvantageState(models.Model):
    campaign_system = models.OneToOneField(
        CampaignSystem,
        on_delete=models.CASCADE,
        related_name="advantage_state",
    )
    as_of = models.DateTimeField(default=timezone.now)
    our_pct = models.FloatField(default=0)
    enemy_pct = models.FloatField(default=0)
    basis = models.CharField(
        max_length=16,
        choices=(
            ("reading", "Pilot reading"),
            ("estimate", "Estimate"),
            ("unknown", "Unknown"),
        ),
        default="unknown",
    )
    reading_age_minutes = models.IntegerField(null=True, blank=True)
    source = models.CharField(max_length=16, default="pilot")
    our_generated_since_reading = models.FloatField(default=0)
    enemy_removed_since_reading = models.FloatField(default=0)

    @property
    def is_stale(self) -> bool:
        return (
            self.reading_age_minutes is None or self.reading_age_minutes > 180
        )

    @property
    def net_pct(self) -> float:
        return self.our_pct - self.enemy_pct


class CampaignKillmail(models.Model):
    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="killmails"
    )
    killmail_id = models.BigIntegerField(db_index=True)
    killmail_hash = models.CharField(max_length=64, blank=True, default="")
    killmail_time = models.DateTimeField(db_index=True)
    solar_system_id = models.BigIntegerField(db_index=True)

    victim_character_id = models.BigIntegerField(null=True, blank=True)
    victim_character_name = models.CharField(
        max_length=255, blank=True, default=""
    )
    victim_corporation_id = models.BigIntegerField(null=True, blank=True)
    victim_alliance_id = models.BigIntegerField(null=True, blank=True)
    victim_faction_id = models.BigIntegerField(null=True, blank=True)
    victim_ship_type_id = models.BigIntegerField(null=True, blank=True)
    # Whoever landed the final blow; the feed names them by id only.
    killer_character_id = models.BigIntegerField(null=True, blank=True)
    killer_character_name = models.CharField(
        max_length=255, blank=True, default=""
    )
    killer_faction_id = models.BigIntegerField(null=True, blank=True)

    isk_value = models.BigIntegerField(default=0)
    is_pod = models.BooleanField(default=False)
    is_solo = models.BooleanField(default=False)
    is_structure = models.BooleanField(default=False, db_index=True)
    is_capital = models.BooleanField(default=False, db_index=True)
    structure = models.ForeignKey(
        "CampaignStructure",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="killmails",
    )
    attacker_count = models.PositiveIntegerField(default=0)
    enlisted_attacker_count = models.PositiveIntegerField(default=0)
    outcome = models.CharField(
        max_length=16,
        choices=KillmailOutcome.choices,
        default=KillmailOutcome.UNSCORED,
        db_index=True,
    )
    fleet = models.ForeignKey(
        "fleets.EveFleet", on_delete=models.SET_NULL, null=True, blank=True
    )

    sources = models.JSONField(default=list, blank=True)
    first_seen_via = models.CharField(max_length=24, blank=True, default="")
    on_zkillboard = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-killmail_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "killmail_id"],
                name="campaign_killmail_unique",
            )
        ]
        indexes = [
            models.Index(fields=["campaign", "-killmail_time"]),
            models.Index(fields=["campaign", "outcome", "-killmail_time"]),
        ]

    def __str__(self) -> str:
        return f"{self.outcome} {self.killmail_id}"


class CampaignKillmailParticipant(models.Model):
    """Only stored when an enlisted pilot is on the mail."""

    killmail = models.ForeignKey(
        CampaignKillmail, on_delete=models.CASCADE, related_name="participants"
    )
    character_id = models.BigIntegerField(db_index=True)
    character_name = models.CharField(max_length=255, blank=True, default="")
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    enlisted = models.BooleanField(default=False)
    role = models.CharField(
        max_length=8,
        choices=(("attacker", "Attacker"), ("victim", "Victim")),
        default="attacker",
    )
    ship_type_id = models.BigIntegerField(null=True, blank=True)
    damage_done = models.BigIntegerField(default=0)
    final_blow = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["killmail", "character_id"],
                name="campaign_killmail_participant_unique",
            )
        ]


class CampaignSiteCompletion(models.Model):
    """One LP payout attributed to a campaign, pilot and system."""

    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="site_completions"
    )
    payout = models.OneToOneField(
        "eveonline.EveCharacterFwLpPayout", on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    character_id = models.BigIntegerField(null=True, blank=True)
    campaign_system = models.ForeignKey(
        CampaignSystem,
        on_delete=models.CASCADE,
        related_name="site_completions",
    )
    occurred_at = models.DateTimeField(db_index=True)
    amount_lp = models.IntegerField(default=0)
    event_code = models.IntegerField(db_index=True)
    site_kind = models.CharField(
        max_length=24, choices=SiteKind.choices, default=SiteKind.UNKNOWN
    )
    complex = models.ForeignKey(
        "CampaignComplexCompletion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payouts",
    )
    scored = models.BooleanField(
        default=True,
        help_text="False while the payout's event code is unconfirmed. The "
        "completion is still shown, it just cannot move anyone's standing.",
    )

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [models.Index(fields=["campaign", "-occurred_at"])]

    def __str__(self) -> str:
        return f"{self.site_kind} {self.amount_lp} LP"

    @property
    def advantage_delta(self) -> tuple[float, float]:
        """(our advantage generated, enemy advantage removed)."""
        return ADVANTAGE_DELTA_BY_SITE_KIND.get(self.site_kind, (0.0, 0.0))


class CampaignComplexCompletion(models.Model):
    """One complex capture, recovered from the payouts that share a site id."""

    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="complex_completions"
    )
    campaign_system = models.ForeignKey(
        CampaignSystem, on_delete=models.CASCADE, related_name="complexes"
    )
    site_ref = models.BigIntegerField(db_index=True)
    completed_at = models.DateTimeField(db_index=True)
    split_count = models.PositiveSmallIntegerField(default=1)
    operational_state = models.CharField(
        max_length=24,
        choices=OperationalState.choices,
        default=OperationalState.UNKNOWN,
    )
    contested_factor = models.FloatField(default=1.0)
    suppression_used = models.FloatField(default=1.0)
    base_lp_tier = models.IntegerField(null=True, blank=True)
    inferred_plex_class = models.CharField(
        max_length=32, blank=True, default=""
    )
    class_candidates = models.JSONField(default=list, blank=True)
    confidence = models.CharField(
        max_length=8,
        choices=(
            ("high", "High"),
            ("low", "Low"),
            ("unknown", "Unknown"),
        ),
        default="unknown",
    )

    class Meta:
        ordering = ["-completed_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "site_ref"],
                name="campaign_complex_unique",
            )
        ]

    def __str__(self) -> str:
        return f"{self.inferred_plex_class or 'complex'} in {self.campaign_system}"


class CampaignParticipantDay(models.Model):
    """The only table the boards read. One row per pilot per campaign day."""

    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="participant_days"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    day = models.DateField(db_index=True)

    kills = models.PositiveIntegerField(default=0)
    losses = models.PositiveIntegerField(default=0)
    solo_kills = models.PositiveIntegerField(default=0)
    final_blows = models.PositiveIntegerField(default=0)
    gang_kills = models.PositiveIntegerField(default=0)
    structure_kills = models.PositiveIntegerField(default=0)
    structure_losses = models.PositiveIntegerField(default=0)
    capital_kills = models.PositiveIntegerField(default=0)
    capital_losses = models.PositiveIntegerField(default=0)
    isk_destroyed = models.BigIntegerField(default=0)
    isk_lost = models.BigIntegerField(default=0)

    complexes = models.PositiveIntegerField(default=0)
    advantage_sites = models.PositiveIntegerField(default=0)
    supply_caches = models.PositiveIntegerField(default=0)
    battlefields = models.PositiveIntegerField(default=0)
    advantage_generated = models.FloatField(default=0)
    enemy_advantage_removed = models.FloatField(default=0)
    advantage_readings = models.PositiveIntegerField(default=0)

    fleets_attended = models.PositiveIntegerField(default=0)
    fleets_led = models.PositiveIntegerField(default=0)
    gangs_led = models.PositiveIntegerField(default=0)
    standing_fleet_minutes = models.PositiveIntegerField(default=0)
    standing_fleet_day = models.BooleanField(default=False)

    orders_completed = models.PositiveIntegerField(default=0)
    supply_isk_delivered = models.BigIntegerField(default=0)
    project_isk_earned = models.BigIntegerField(default=0)

    points = models.IntegerField(default=0)
    active = models.BooleanField(default=False, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-day"]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "user", "day"],
                name="campaign_participant_day_unique",
            )
        ]
        indexes = [
            models.Index(fields=["campaign", "day", "-points"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} {self.day} ({self.points} pts)"


class CampaignParticipantStat(models.Model):
    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="participant_stats"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    points = models.IntegerField(default=0)
    kills = models.PositiveIntegerField(default=0)
    losses = models.PositiveIntegerField(default=0)
    isk_destroyed = models.BigIntegerField(default=0)
    isk_lost = models.BigIntegerField(default=0)
    complexes = models.PositiveIntegerField(default=0)
    advantage_sites = models.PositiveIntegerField(default=0)
    advantage_generated = models.FloatField(default=0)
    fleets_attended = models.PositiveIntegerField(default=0)
    standing_fleet_minutes = models.PositiveIntegerField(default=0)
    active_days = models.PositiveIntegerField(default=0)

    streak_days = models.PositiveIntegerField(default=0)
    best_streak_days = models.PositiveIntegerField(default=0)
    shields_used_this_week = models.PositiveSmallIntegerField(default=0)
    last_active_day = models.DateField(null=True, blank=True)

    rank_points = models.PositiveIntegerField(null=True, blank=True)
    characters_included = models.PositiveSmallIntegerField(default=0)
    characters_tracked = models.PositiveSmallIntegerField(default=0)
    characters_lapsed = models.PositiveSmallIntegerField(default=0)

    active_hours_utc = models.JSONField(default=list, blank=True)
    observed_prime_time = models.CharField(
        max_length=16, blank=True, default=""
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-points"]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "user"],
                name="campaign_participant_stat_unique",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} {self.points} pts"


class CampaignEvent(models.Model):
    """The campaign timeline, including mirrored events from the feed."""

    class Kind(models.TextChoices):
        CAMPAIGN_STARTED = "campaign_started", "Campaign started"
        CAMPAIGN_COMPLETED = "campaign_completed", "Campaign completed"
        SYSTEM_THRESHOLD = "system_threshold", "System near threshold"
        SYSTEM_FLIPPED = "system_flipped", "System flipped"
        FLEET_ACTIVE = "fleet_active", "Fleet active"
        HOSTILE_GANG = "hostile_gang", "Hostile gang detected"
        KILLMAIL_BATCH = "killmail_batch", "Kill burst"
        CONTESTED_CHANGE = "contested_change", "Contested change"
        GANG_FORMED = "gang_formed", "Gang formed"
        STANDING_FLEET_TAKEN = "standing_fleet_taken", "Standing fleet taken"
        AWARD = "award", "Award"
        WEEK_PLAN = "week_plan", "Weekly plan"
        MILESTONE = "milestone", "Milestone"

    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="events"
    )
    kind = models.CharField(max_length=32, choices=Kind.choices)
    occurred_at = models.DateTimeField(db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    title = models.CharField(max_length=256, blank=True, default="")
    body = models.TextField(blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)
    campaign_system = models.ForeignKey(
        CampaignSystem, on_delete=models.SET_NULL, null=True, blank=True
    )
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    side = models.CharField(
        max_length=16,
        choices=(
            ("friendly", "Friendly"),
            ("hostile", "Hostile"),
            ("neutral", "Neutral"),
        ),
        default="neutral",
    )
    source = models.CharField(
        max_length=16,
        choices=(("campaign", "Campaign"), ("feed", "Feed")),
        default="campaign",
    )
    feed_event = models.ForeignKey(
        "feed.FeedEvent",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campaign_events",
    )
    fleet = models.ForeignKey(
        "fleets.EveFleet", on_delete=models.SET_NULL, null=True, blank=True
    )
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ["-occurred_at", "-id"]
        indexes = [models.Index(fields=["campaign", "-occurred_at"])]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "feed_event"],
                name="campaign_feed_event_unique",
            )
        ]

    def __str__(self) -> str:
        return f"{self.kind} {self.occurred_at:%Y-%m-%d %H:%M}"


class CampaignAward(models.Model):
    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="awards"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=32)
    label = models.CharField(max_length=64)
    awarded_at = models.DateTimeField(default=timezone.now)
    payload = models.JSONField(default=dict, blank=True)
    scope = models.CharField(
        max_length=8,
        choices=(("campaign", "Campaign"), ("week", "Week")),
        default="week",
    )
    week_start = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-awarded_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "code", "week_start"],
                name="campaign_award_week_unique",
            ),
            # MySQL treats NULLs as distinct, so the constraint above does
            # not cover the campaign awards, whose week_start is null.
            models.UniqueConstraint(
                fields=["campaign", "code"],
                condition=models.Q(week_start__isnull=True),
                name="campaign_award_final_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.label} — {self.user}"
