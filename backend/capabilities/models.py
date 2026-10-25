"""
Materialized capability data. Nothing here is computed in a request:
Celery tasks in capabilities.tasks fill every table.
"""

from django.contrib.auth.models import User
from django.db import models

from eveonline.models import EveCharacter
from fittings.models import FITTING_CAPABILITY_CHOICES as CAPABILITY_CHOICES
from fittings.models import EveFitting


class SdeSnapshot(models.Model):
    """The slice of CCP's SDE the engine reads, one row per build."""

    build = models.IntegerField(unique=True)
    release_date = models.CharField(max_length=64, blank=True)
    loaded_at = models.DateTimeField(auto_now_add=True)
    is_current = models.BooleanField(default=False, db_index=True)
    data = models.BinaryField(
        help_text="zlib-compressed JSON (engine.sde.pack)"
    )
    size = models.IntegerField(default=0)
    changes = models.JSONField(
        default=dict,
        blank=True,
        help_text="What this build changed: fittings and readiness counts.",
    )

    class Meta:
        ordering = ["-build"]

    def __str__(self):
        return f"SDE {self.build}{' (current)' if self.is_current else ''}"


class FittingRequirementSet(models.Model):
    """Skill requirements for one fitting version, SDE build and rule set."""

    fitting = models.ForeignKey(
        EveFitting, on_delete=models.CASCADE, related_name="requirement_sets"
    )
    fitting_version = models.CharField(max_length=255, blank=True)
    sde_build = models.IntegerField()
    rules_version = models.IntegerField()
    input_key = models.CharField(
        max_length=64,
        help_text="Hash of everything the result depends on; unchanged means no recompute.",
    )
    capability = models.CharField(max_length=16, choices=CAPABILITY_CHOICES)
    capability_source = models.CharField(max_length=16, default="auto")
    strategic = models.BooleanField(
        default=False,
        help_text="In a strategic doctrine: Doctrine-ready needs the core tier.",
    )
    tank_layers = models.JSONField(default=list)
    alternatives = models.JSONField(default=dict, blank=True)
    alternative_requirements = models.JSONField(default=dict, blank=True)
    unknown_items = models.JSONField(default=list, blank=True)
    proven_pilots = models.IntegerField(default=0)
    proven_pass_rate = models.FloatField(null=True, blank=True)
    computed_at = models.DateTimeField(auto_now=True)
    is_current = models.BooleanField(default=True)

    class Meta:
        indexes = [models.Index(fields=["fitting", "is_current"])]

    def __str__(self):
        return f"{self.fitting.name} ({self.capability}, SDE {self.sde_build})"


class FittingSkillRequirement(models.Model):
    """One skill of a fitting: required <= core <= optimal levels."""

    requirement_set = models.ForeignKey(
        FittingRequirementSet, on_delete=models.CASCADE, related_name="rows"
    )
    skill_id = models.IntegerField()
    skill_name = models.CharField(max_length=255)
    required_level = models.SmallIntegerField(default=0)
    fit_level = models.SmallIntegerField(
        default=0,
        help_text="Level a pilot with only the required skills needs to fit it.",
    )
    core_level = models.SmallIntegerField(default=0)
    optimal_level = models.SmallIntegerField(default=0)
    sources = models.JSONField(default=dict)
    bucket = models.CharField(max_length=16, blank=True)
    per_level_bonus = models.FloatField(default=0)
    weight = models.FloatField(default=0)
    reason = models.CharField(max_length=255, blank=True)
    mastery_levels = models.CharField(max_length=5, blank=True)
    empirical_level = models.SmallIntegerField(null=True, blank=True)
    proven_meeting_core = models.FloatField(null=True, blank=True)
    overridden = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["requirement_set", "skill_id"],
                name="unique_requirement_set_skill",
            )
        ]

    @property
    def tier(self) -> str:
        if self.required_level or self.fit_level:
            return "required"
        if self.core_level:
            return "core"
        return "optimal"

    def __str__(self):
        return f"{self.skill_name} {self.required_level}/{self.core_level}/{self.optimal_level}"


class CharacterFittingReadiness(models.Model):
    character = models.ForeignKey(
        EveCharacter,
        on_delete=models.CASCADE,
        related_name="fitting_readiness",
    )
    fitting = models.ForeignKey(
        EveFitting,
        on_delete=models.CASCADE,
        related_name="character_readiness",
    )
    requirement_set = models.ForeignKey(
        FittingRequirementSet, on_delete=models.CASCADE, related_name="+"
    )
    unlocked = models.BooleanField(default=False)
    hard_ready = models.BooleanField(default=False)
    core_ready = models.BooleanField(default=False)
    doctrine_ready = models.BooleanField(
        default=False,
        help_text="Core-ready for strategic fittings, hard-ready otherwise.",
    )
    missing_required = models.JSONField(default=list, blank=True)
    missing_core = models.JSONField(default=list, blank=True)
    fit_problems = models.JSONField(default=list, blank=True)
    days_to_hard = models.FloatField(default=0)
    days_to_core = models.FloatField(default=0)
    support_score = models.SmallIntegerField(default=0)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["character", "fitting"],
                name="unique_character_fitting_readiness",
            )
        ]
        indexes = [
            models.Index(fields=["fitting", "doctrine_ready"]),
            models.Index(fields=["fitting", "hard_ready"]),
        ]


class CharacterCapability(models.Model):
    LEVEL_NONE = 0
    LEVEL_UNLOCKED = 1
    LEVEL_DOCTRINE_READY = 2
    LEVEL_PROVEN = 3
    LEVEL_CHOICES = [
        (LEVEL_NONE, "None"),
        (LEVEL_UNLOCKED, "Unlocked"),
        (LEVEL_DOCTRINE_READY, "Doctrine-ready"),
        (LEVEL_PROVEN, "Proven"),
    ]

    character = models.ForeignKey(
        EveCharacter, on_delete=models.CASCADE, related_name="capabilities"
    )
    capability = models.CharField(max_length=16, choices=CAPABILITY_CHOICES)
    level = models.SmallIntegerField(choices=LEVEL_CHOICES, default=LEVEL_NONE)
    best_fitting = models.ForeignKey(
        EveFitting,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    ready_fittings = models.IntegerField(default=0)
    unlocked_fittings = models.IntegerField(default=0)
    fleets_365d = models.IntegerField(default=0)
    strategic_fleets_365d = models.IntegerField(default=0)
    last_flown = models.DateTimeField(null=True, blank=True)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["character", "capability"],
                name="unique_character_capability",
            )
        ]
        indexes = [models.Index(fields=["capability", "level"])]


class CharacterAccount(models.Model):
    """One EVE account of a player: up to three characters."""

    SOURCE_INFERRED = "inferred"
    SOURCE_PILOT = "pilot"

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="character_accounts"
    )
    number = models.SmallIntegerField()
    source = models.CharField(max_length=16, default=SOURCE_INFERRED)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user", "number"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "number"], name="unique_user_account_number"
            )
        ]

    def __str__(self):
        return f"Account {self.number}"


class CharacterAccountMember(models.Model):
    """Where a character sits. A pilot can also say "not on an account"
    (no account): inference then leaves the character alone."""

    character = models.OneToOneField(
        EveCharacter,
        on_delete=models.CASCADE,
        related_name="account_membership",
    )
    account = models.ForeignKey(
        CharacterAccount,
        on_delete=models.CASCADE,
        related_name="members",
        null=True,
        blank=True,
    )
    source = models.CharField(
        max_length=16, default=CharacterAccount.SOURCE_INFERRED
    )


class CharacterAccountLink(models.Model):
    """Two of a player's characters seen in one fleet at the same time.

    EVE allows one character online per account, so a link proves they are
    on different accounts.
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="character_account_links"
    )
    character_a = models.ForeignKey(
        EveCharacter, on_delete=models.CASCADE, related_name="+"
    )
    character_b = models.ForeignKey(
        EveCharacter, on_delete=models.CASCADE, related_name="+"
    )
    fleets_together = models.IntegerField(default=0)
    last_seen_together = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["character_a", "character_b"],
                name="unique_character_account_link",
            )
        ]


class CapabilitySkill(models.Model):
    """Rank and prerequisites of every skill, from the current SDE build.

    Training plans read this in a request instead of loading the SDE.
    """

    skill_id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    rank = models.FloatField(default=1)
    prerequisites = models.JSONField(
        default=dict, blank=True, help_text="{skill id: level}"
    )
    sde_build = models.IntegerField(default=0)

    def __str__(self):
        return str(self.name)


class CharacterShipGoal(models.Model):
    """A doctrine fit a pilot is training one character for.

    One ship trains at a time: the first goal by position that isn't
    ready is the one in training, the rest wait in order.
    """

    TARGET_READY = "ready"
    TARGET_OPTIMAL = "optimal"
    TARGET_CHOICES = [
        (TARGET_READY, "Ready"),
        (TARGET_OPTIMAL, "Optimal"),
    ]

    character = models.ForeignKey(
        EveCharacter, on_delete=models.CASCADE, related_name="ship_goals"
    )
    fitting = models.ForeignKey(
        EveFitting, on_delete=models.CASCADE, related_name="+"
    )
    position = models.IntegerField(default=0)
    target = models.CharField(
        max_length=16, choices=TARGET_CHOICES, default=TARGET_READY
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["character", "position", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["character", "fitting"],
                name="unique_character_ship_goal",
            )
        ]

    def __str__(self):
        return f"{self.character} → {self.fitting.name}"


class CharacterTrainingSettings(models.Model):
    character = models.OneToOneField(
        EveCharacter,
        on_delete=models.CASCADE,
        related_name="training_settings",
    )
    not_for_fleets = models.BooleanField(
        default=False,
        help_text="A cyno, market or hauling alt: no suggestions, left out of counts.",
    )
    updated_at = models.DateTimeField(auto_now=True)
