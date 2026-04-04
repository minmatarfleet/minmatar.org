import uuid

from django.core.exceptions import ValidationError
from django.db import models

from app.models import MinmatarSoftDeleteModel
from eveonline.models import EveLocation


class FittingTag(models.TextChoices):
    HIGHSEC = "highsec", "Highsec"
    LOWSEC = "lowsec", "Lowsec"
    NULLSEC = "nullsec", "Nullsec"
    FACTION_WARFARE = "faction_warfare", "Faction warfare"
    SOLO = "solo", "Solo"
    NANOGANG = "nanogang", "Nanogang"
    FLEET_COMPOSITION = "fleet_composition", "Fleet Composition"
    NEW_PLAYER_FRIENDLY = "new_player_friendly", "New Player Friendly"
    BUDGET = "budget", "Budget"
    ESCAPE_FRIGATE = "escape_frigate", "Escape Frigate"


# Fields that define “the fit” for versioning; changes bump latest_version and may write history.
EVE_FITTING_VERSIONED_FIELDS = (
    "eft_format",
    "description",
    "aliases",
    "minimum_pod",
    "recommended_pod",
    "tags",
)


def _eve_fitting_versioned_field_equal(field: str, old_val, new_val) -> bool:
    if field == "tags":
        old_list = old_val if isinstance(old_val, list) else []
        new_list = new_val if isinstance(new_val, list) else []
        return sorted(old_list) == sorted(new_list)
    return (old_val or "") == (new_val or "")


class EveFitting(MinmatarSoftDeleteModel):
    """
    Model for storing fittings
    """

    name = models.CharField(max_length=255)
    ship_id = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    description = models.TextField()
    # comma separated list of aliases
    # e.g [FL33T] Tornado, [NVY-30] Tornado
    aliases = models.TextField(blank=True, null=True)

    # fitting info
    eft_format = models.TextField()
    latest_version = models.CharField(max_length=255, blank=True)

    minimum_pod = models.TextField(blank=True)
    recommended_pod = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                condition=models.Q(deleted__isnull=True),
                name="unique_evefitting_name_not_deleted",
            ),
        ]

    def __str__(self):
        return str(self.name)

    @staticmethod
    def coerce_tags(raw):
        """Validate tags and return a sorted list of unique allowed values."""
        if raw is None:
            return []
        if not isinstance(raw, list):
            raise ValidationError("tags must be a list")
        allowed = {c.value for c in FittingTag}
        seen = set()
        out = []
        for item in raw:
            if not isinstance(item, str):
                raise ValidationError("each tag must be a string")
            if item not in allowed:
                raise ValidationError(f"invalid fitting tag: {item!r}")
            if item not in seen:
                seen.add(item)
                out.append(item)
        out.sort()
        return out

    def clean(self):
        super().clean()
        try:
            self.tags = self.coerce_tags(self.tags)
        except ValidationError as e:
            raise ValidationError({"tags": list(e.messages)}) from e

    def save(self, *args, **kwargs):
        self.tags = self.coerce_tags(self.tags)
        fitting_name = self.fitting_name_from_eft(self.eft_format)
        if self.name != fitting_name:
            raise ValidationError(
                f"Name '{self.name}' does not match EFT name '{fitting_name}'"
            )

        if self.pk is None:
            if not self.latest_version:
                self.latest_version = str(uuid.uuid4())
        else:
            old = (
                EveFitting.all_objects.filter(pk=self.pk)
                .values(
                    *EVE_FITTING_VERSIONED_FIELDS,
                    "latest_version",
                    "name",
                    "ship_id",
                )
                .first()
            )
            if old:
                versioned_changed = any(
                    not _eve_fitting_versioned_field_equal(
                        f, old.get(f), getattr(self, f)
                    )
                    for f in EVE_FITTING_VERSIONED_FIELDS
                )
                if versioned_changed:
                    if old["latest_version"]:
                        old_tags = old.get("tags")
                        if not isinstance(old_tags, list):
                            old_tags = []
                        EveFittingHistory.objects.create(
                            fitting_id=self.pk,
                            superseded_version_id=old["latest_version"],
                            name=old["name"],
                            ship_id=old["ship_id"],
                            eft_format=old["eft_format"],
                            description=old["description"],
                            aliases=old["aliases"],
                            minimum_pod=old["minimum_pod"],
                            recommended_pod=old["recommended_pod"],
                            tags=old_tags,
                        )
                    self.latest_version = str(uuid.uuid4())

        super().save(*args, **kwargs)

    @staticmethod
    def ship_name_from_eft(eft_format):
        """Extract ship name from the first line of EFT format [ShipName, Fitting name]."""
        first_line = eft_format.split("\n")[0]
        return first_line.split(",")[0].strip().strip("[]")

    @staticmethod
    def fitting_name_from_eft(eft_format):
        """Extract fitting name from the first line of EFT format [ShipName, Fitting name]."""
        if not (eft_format and eft_format.strip()):
            return ""
        parts = eft_format.split("\n")[0].split(",", 1)
        if len(parts) < 2:
            return ""
        fitting_name = parts[1].strip()
        if fitting_name.endswith("]"):
            fitting_name = fitting_name[:-1].strip()
        return fitting_name


class EveFittingHistory(models.Model):
    """
    Snapshot of an EveFitting before a versioned change. superseded_version_id is the
    latest_version UUID that was replaced.
    """

    fitting = models.ForeignKey(
        EveFitting,
        on_delete=models.CASCADE,
        related_name="version_history",
    )
    superseded_version_id = models.CharField(max_length=255, blank=True)
    name = models.CharField(max_length=255)
    ship_id = models.IntegerField()
    eft_format = models.TextField()
    description = models.TextField()
    aliases = models.TextField(blank=True, null=True)
    minimum_pod = models.TextField(blank=True)
    recommended_pod = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        vid = self.superseded_version_id or "—"
        return f"{self.fitting.name} ({vid[:8]})"


class EveFittingRefit(models.Model):
    """
    A refit of an EveFitting: the same ship with the same slot layout (same contents)
    but different modules fitted. The refit's EFT must describe the same ship as the
    base fitting.
    """

    base_fitting = models.ForeignKey(
        EveFitting, on_delete=models.CASCADE, related_name="refits"
    )
    name = models.CharField(max_length=255)
    eft_format = models.TextField()
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["base_fitting", "name"]]
        ordering = ["base_fitting", "name"]

    def __str__(self):
        return f"{self.base_fitting.name} — {self.name}"

    def save(self, *args, **kwargs):
        base_ship = EveFitting.ship_name_from_eft(self.base_fitting.eft_format)
        refit_ship = EveFitting.ship_name_from_eft(self.eft_format)
        if base_ship != refit_ship:
            raise ValidationError(
                f"Refit ship '{refit_ship}' must match base fitting ship '{base_ship}'"
            )
        super().save(*args, **kwargs)


class EveDoctrine(models.Model):
    """
    Model for storing doctrines
    """

    type_choices = (
        ("non_strategic", "Non strategic"),
        ("training", "Training"),
        ("strategic", "Strategic"),
    )
    name = models.CharField(max_length=255, unique=True)
    type = models.CharField(max_length=255, choices=type_choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    description = models.TextField()
    locations = models.ManyToManyField(EveLocation, blank=True)

    @property
    def doctrine_link(self):
        return f"https://my.minmatar.org/ships/doctrines/list/{self.id}"

    def __str__(self):
        return str(self.name)


class EveDoctrineFitting(models.Model):
    """
    Model for storing fittings in a doctrine
    """

    role_choices = (
        ("primary", "Primary"),
        ("secondary", "Secondary"),
        ("support", "Support"),
    )

    doctrine = models.ForeignKey(EveDoctrine, on_delete=models.CASCADE)
    fitting = models.ForeignKey(EveFitting, on_delete=models.CASCADE)
    role = models.CharField(max_length=255, choices=role_choices)

    def __str__(self):
        return f"{self.doctrine.name} - {self.fitting.name}"
