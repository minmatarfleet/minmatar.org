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

from campaigns.constants import ADVANTAGE_DELTA_BY_SITE_KIND

# The campaign week and campaign day both roll over at 11:00 UTC, which is
# shortly after EVE's daily downtime and the moment FW victory points reset.
DAY_BOUNDARY_HOUR = 11


class CampaignStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SCHEDULED = "scheduled", "Scheduled"
    ACTIVE = "active", "Active"
    COMPLETED = "completed", "Completed"
    ARCHIVED = "archived", "Archived"


class SystemGoal(models.TextChoices):
    CAPTURE = "capture", "Capture"
    DEFEND = "defend", "Defend"
    CONTEST = "contest", "Contest"
    NONE = "none", "No goal"


class SystemRole(models.TextChoices):
    PRIMARY = "primary", "Primary"
    SECONDARY = "secondary", "Secondary"
    SUPPORT = "support", "Support"


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
    """One named operation over a set of warzone systems."""

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
    cover_image_url = models.CharField(max_length=512, blank=True, default="")

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


class CampaignSystem(models.Model):
    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="systems"
    )
    solar_system_id = models.BigIntegerField(db_index=True)
    name = models.CharField(max_length=64)
    region_id = models.BigIntegerField(null=True, blank=True)
    role = models.CharField(
        max_length=16, choices=SystemRole.choices, default=SystemRole.PRIMARY
    )
    goal = models.CharField(
        max_length=16, choices=SystemGoal.choices, default=SystemGoal.CAPTURE
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
    vp_needed_at_start = models.BigIntegerField(null=True, blank=True)

    def __str__(self) -> str:
        return f"Arc for {self.campaign_system}"


class CampaignWeekTarget(models.Model):
    """Auto-proposed weekly target; an operator accepts or nudges it."""

    class Metric(models.TextChoices):
        VICTORY_POINTS = "victory_points", "Victory points"
        DAYS_UNDER_LINE = "days_under_line", "Days under contest line"
        ADVANTAGE = "advantage", "Advantage generated"

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
    def pace(self) -> str:
        """on_pace / behind / ahead — never red before the week is done."""
        if self.target <= 0:
            return "on_pace"
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


class CampaignStandingFleet(models.Model):
    """The always-open fleet that is the campaign's front door."""

    campaign = models.OneToOneField(
        Campaign, on_delete=models.CASCADE, related_name="standing_fleet"
    )
    fleet = models.ForeignKey(
        "fleets.EveFleet", on_delete=models.SET_NULL, null=True, blank=True
    )
    current_boss_character_id = models.BigIntegerField(null=True, blank=True)
    current_boss_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    taken_at = models.DateTimeField(null=True, blank=True)
    handovers = models.PositiveIntegerField(default=0)
    uptime_minutes_today = models.PositiveIntegerField(default=0)
    uptime_minutes_prime_today = models.PositiveIntegerField(default=0)
    advert_name = models.CharField(max_length=128, blank=True, default="")
    voice_channel_id = models.BigIntegerField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    member_count = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return f"Standing fleet for {self.campaign.slug}"

    @property
    def is_up(self) -> bool:
        if not self.current_boss_character_id or not self.last_seen_at:
            return False
        return (timezone.now() - self.last_seen_at).total_seconds() < 600


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
        choices=(("pilot", "Pilot"), ("manager", "Manager")),
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
    victim_ship_type_id = models.BigIntegerField(null=True, blank=True)

    isk_value = models.BigIntegerField(default=0)
    is_pod = models.BooleanField(default=False)
    is_solo = models.BooleanField(default=False)
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
