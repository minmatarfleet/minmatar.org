import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from app.models import MinmatarSoftDeleteModel
from eveonline.models import EveLocation
from eveuniverse.models import EveType


class FittingTag(models.TextChoices):
    HIGHSEC = "highsec", "Highsec"
    NULLSEC = "nullsec", "Nullsec"
    FACTION_WARFARE = "faction_warfare", "Faction warfare"
    NANOGANG = "nanogang", "Nanogang"
    FLEET_COMPOSITION = "fleet_composition", "Fleet Composition"
    NEW_PLAYER_FRIENDLY = "new_player_friendly", "New Player Friendly"
    CAPITALS = "capitals", "Capitals"
    COMMAND_BURSTS = "command_bursts", "Command Bursts"
    INDUSTRY = "industry", "Industry"
    ESCAPE_FRIGATE = "escape_frigate", "Escape Frigate"


class KnownFitting(models.TextChoices):
    """Stable catalog keys for fittings the app/guides resolve by meaning."""

    # Navy destroyer metagame guide
    GUIDE_NAVY_DESTROYER_CAT_BLASTER = (
        "guide.navy-destroyer.cat-blaster",
        "Blaster Catalyst Navy Issue",
    )
    GUIDE_NAVY_DESTROYER_CAT_10MN = (
        "guide.navy-destroyer.cat-10mn",
        "10mn Catalyst Navy Issue",
    )
    GUIDE_NAVY_DESTROYER_COERCER_DUAL_NEUTS_MWD = (
        "guide.navy-destroyer.coercer-dual-neuts-mwd",
        "2X Neut Coercer Navy Issue",
    )
    GUIDE_NAVY_DESTROYER_COERCER_MWD_SCRAM_BRAWL = (
        "guide.navy-destroyer.coercer-mwd-scram-brawl",
        "Pulse Coercer Navy Issue",
    )
    GUIDE_NAVY_DESTROYER_COERCER_KITE_BEAMS = (
        "guide.navy-destroyer.coercer-kite-beams",
        "Beam Coercer Navy Issue",
    )
    GUIDE_NAVY_DESTROYER_TFI_AC = (
        "guide.navy-destroyer.tfi-ac",
        "AC Thrasher Fleet Issue",
    )
    GUIDE_NAVY_DESTROYER_TFI_ARTY = (
        "guide.navy-destroyer.tfi-arty",
        "Arty Thrasher Fleet Issue",
    )
    GUIDE_NAVY_DESTROYER_CORM_DUAL_MASB_NEUTRONS = (
        "guide.navy-destroyer.corm-dual-masb-neutrons",
        "Dual MASB Cormorant Navy Issue",
    )
    GUIDE_NAVY_DESTROYER_CORM_BUFFER = (
        "guide.navy-destroyer.corm-buffer",
        "Buffer Cormorant Navy Issue",
    )
    GUIDE_NAVY_DESTROYER_CORM_10MN = (
        "guide.navy-destroyer.corm-10mn",
        "10mn Cormorant Navy Issue",
    )
    GUIDE_NAVY_DESTROYER_TALFI_10MN_ROCKET = (
        "guide.navy-destroyer.talfi-10mn-rocket",
        "10mn Talwar Fleet Issue",
    )
    GUIDE_NAVY_DESTROYER_ALGOS_10MN = (
        "guide.navy-destroyer.algos-10mn",
        "10mn Algos",
    )
    GUIDE_NAVY_DESTROYER_ALGOS_BRAWL = (
        "guide.navy-destroyer.algos-brawl",
        "Brawl Algos",
    )
    GUIDE_NAVY_DESTROYER_ALGOS_FARM = (
        "guide.navy-destroyer.algos-farm",
        "Farm Algos",
    )
    GUIDE_NAVY_DESTROYER_THRASHER_ARTY = (
        "guide.navy-destroyer.thrasher-arty",
        "Arty Thrasher",
    )
    GUIDE_NAVY_DESTROYER_THRASHER_AC = (
        "guide.navy-destroyer.thrasher-ac",
        "AC Thrasher",
    )
    GUIDE_NAVY_DESTROYER_COERCER_BRAWL = (
        "guide.navy-destroyer.coercer-brawl",
        "Brawl Coercer",
    )
    GUIDE_NAVY_DESTROYER_DRAGOON_NEUT = (
        "guide.navy-destroyer.dragoon-neut",
        "Neut Dragoon",
    )

    # Navy frigate guide
    GUIDE_NAVY_FRIGATE_HOOKBILL_SHIELD = (
        "guide.navy-frigate.hookbill-shield",
        "Scram Kite — Shield",
    )
    GUIDE_NAVY_FRIGATE_HOOKBILL_CONTROL = (
        "guide.navy-frigate.hookbill-control",
        "Scram Kite — Control",
    )
    GUIDE_NAVY_FRIGATE_COMET_BLASTER = (
        "guide.navy-frigate.comet-blaster",
        "Blaster Comet",
    )
    GUIDE_NAVY_FRIGATE_COMET_RAIL = (
        "guide.navy-frigate.comet-rail",
        "Rail Comet",
    )
    GUIDE_NAVY_FRIGATE_SLICER_BEAM = (
        "guide.navy-frigate.slicer-beam",
        "Beam Slicer",
    )
    GUIDE_NAVY_FRIGATE_FIRETAIL_ARTY = (
        "guide.navy-frigate.firetail-arty",
        "Arty Firetail",
    )
    GUIDE_NAVY_FRIGATE_VIGIL_WEB_KITE = (
        "guide.navy-frigate.vigil-web-kite",
        "Web Kite Vigil Fleet",
    )
    GUIDE_NAVY_FRIGATE_TRISTAN_BRAWL = (
        "guide.navy-frigate.tristan-brawl",
        "Brawl Tristan",
    )
    GUIDE_NAVY_FRIGATE_BREACHER_MASB = (
        "guide.navy-frigate.breacher-masb",
        "MASB Breacher",
    )

    # Faction warfare cruiser guide
    GUIDE_FW_CRUISER_ARBY_LONG_KITE = (
        "guide.fw-cruiser.arby-long-kite",
        "Long Point Arbitrator",
    )
    GUIDE_FW_CRUISER_ARBY_BRAWL = (
        "guide.fw-cruiser.arby-brawl",
        "Brawl Arbitrator",
    )
    GUIDE_FW_CRUISER_ARBY_TD_SUPPORT = (
        "guide.fw-cruiser.arby-td-support",
        "TD Support Arbitrator",
    )
    GUIDE_FW_CRUISER_AUGNI_POLARIZED = (
        "guide.fw-cruiser.augni-polarized",
        "Polarized Augoror Navy Issue",
    )
    GUIDE_FW_CRUISER_AUGNI_KITE_PULSE = (
        "guide.fw-cruiser.augni-kite-pulse",
        "Pulse Augoror Navy Issue",
    )
    GUIDE_FW_CRUISER_MALLER_PULSE = (
        "guide.fw-cruiser.maller-pulse",
        "Pulse Maller",
    )
    GUIDE_FW_CRUISER_OMEN_QUAD_LIGHT = (
        "guide.fw-cruiser.omen-quad-light",
        "Beam Omen",
    )
    GUIDE_FW_CRUISER_OMEN_KITE_PULSE = (
        "guide.fw-cruiser.omen-kite-pulse",
        "Pulse Omen",
    )
    GUIDE_FW_CRUISER_OMEN_SNIPER = (
        "guide.fw-cruiser.omen-sniper",
        "Sniper Omen",
    )
    GUIDE_FW_CRUISER_OMENNI_MID_KITE = (
        "guide.fw-cruiser.omenni-mid-kite",
        "Kite Omen Navy Issue",
    )
    GUIDE_FW_CRUISER_OMENNI_MID_SNIPER = (
        "guide.fw-cruiser.omenni-mid-sniper",
        "Beam Omen Navy Issue",
    )
    GUIDE_FW_CRUISER_CARACALNI_HAM = (
        "guide.fw-cruiser.caracalni-ham",
        "HAM Caracal Navy Issue",
    )
    GUIDE_FW_CRUISER_OSPREYNI_HAM_NEUT = (
        "guide.fw-cruiser.ospreyni-ham-neut",
        "2X Neut HAM Osprey Navy Issue",
    )
    GUIDE_FW_CRUISER_OSPREYNI_RHML_KITE = (
        "guide.fw-cruiser.ospreyni-rhml-kite",
        "RLML Osprey Navy Issue",
    )
    GUIDE_FW_CRUISER_ENI_BLASTER = (
        "guide.fw-cruiser.eni-blaster",
        "Blaster Exequror Navy Issue",
    )
    GUIDE_FW_CRUISER_ENI_250RAIL = (
        "guide.fw-cruiser.eni-250rail",
        "250mm Rail Exequror Navy Issue",
    )
    GUIDE_FW_CRUISER_ENI_DUAL_PLATE_ELECTRON = (
        "guide.fw-cruiser.eni-dual-plate-electron",
        "Dual Plate Electron Exequror Navy Issue",
    )
    GUIDE_FW_CRUISER_VEXOR_NEUT_PLATE = (
        "guide.fw-cruiser.vexor-neut-plate",
        "Neut Vexor",
    )
    GUIDE_FW_CRUISER_VEXOR_BLASTER_NEUT = (
        "guide.fw-cruiser.vexor-blaster-neut",
        "Blaster Vexor",
    )
    GUIDE_FW_CRUISER_VNI_DUAL_REP = (
        "guide.fw-cruiser.vni-dual-rep",
        "Dual Rep Vexor Navy Issue",
    )
    GUIDE_FW_CRUISER_BELLICOSE_HAM = (
        "guide.fw-cruiser.bellicose-ham",
        "HAM Bellicose",
    )
    GUIDE_FW_CRUISER_BELLICOSE_XLSB = (
        "guide.fw-cruiser.bellicose-xlsb",
        "XLASB HAM Bellicose",
    )
    GUIDE_FW_CRUISER_SCYTHEFI_DUAL_PROP_AC = (
        "guide.fw-cruiser.scythefi-dual-prop-ac",
        "Dual Prop Scythe Fleet Issue",
    )
    GUIDE_FW_CRUISER_SCYTHEFI_RLML_ARMOR = (
        "guide.fw-cruiser.scythefi-rlml-armor",
        "Armor RLML Scythe Fleet Issue",
    )
    GUIDE_FW_CRUISER_SCYTHEFI_RLML_XLSB = (
        "guide.fw-cruiser.scythefi-rlml-xlsb",
        "RLML XLASB Scythe Fleet Issue",
    )
    GUIDE_FW_CRUISER_STABBER_XLSB = (
        "guide.fw-cruiser.stabber-xlsb",
        "AB XLASB Stabber",
    )
    GUIDE_FW_CRUISER_STABBER_VULCAN_KITE = (
        "guide.fw-cruiser.stabber-vulcan-kite",
        "Vulcan Stabber",
    )
    GUIDE_FW_CRUISER_STABBERFI_DUAL_PROP = (
        "guide.fw-cruiser.stabberfi-dual-prop",
        "Dual Prop Stabber Fleet Issue",
    )


DOCTRINE_TYPE_EXPERIMENTAL = "experimental"
DOCTRINE_TYPE_NON_STRATEGIC = "non_strategic"
DOCTRINE_TYPE_STRATEGIC = "strategic"

PROTECTION_TIER_NON_STRATEGIC = "non_strategic"
PROTECTION_TIER_STRATEGIC = "strategic"

# Scalar fields that define “the fit” for versioning (DB columns on EveFitting).
EVE_FITTING_VERSIONED_SCALAR_FIELDS = (
    "eft_format",
    "description",
    "aliases",
    "minimum_pod",
    "recommended_pod",
)

# Versioned payload fields including tags (slug lists in change-request JSON).
EVE_FITTING_VERSIONED_FIELDS = EVE_FITTING_VERSIONED_SCALAR_FIELDS + ("tags",)

EVE_DOCTRINE_VERSIONED_FIELDS = ("name", "type", "description")


def _eve_fitting_versioned_field_equal(field: str, old_val, new_val) -> bool:
    if field == "tags":
        old_list = old_val if isinstance(old_val, list) else []
        new_list = new_val if isinstance(new_val, list) else []
        return sorted(old_list) == sorted(new_list)
    return (old_val or "") == (new_val or "")


def _eve_doctrine_scalar_equal(field: str, old_val, new_val) -> bool:
    return (old_val or "") == (new_val or "")


def composition_snapshot_for_doctrine(doctrine) -> dict:
    """Snapshot primary/secondary/support fitting ids for a doctrine."""
    composition = {"primary": [], "secondary": [], "support": []}
    for row in EveDoctrineFitting.objects.filter(doctrine=doctrine).values(
        "role", "fitting_id"
    ):
        role = row["role"]
        if role in composition:
            composition[role].append(row["fitting_id"])
    for role, fitting_ids in composition.items():
        fitting_ids.sort()
    return composition


def location_ids_for_doctrine(doctrine) -> list:
    return sorted(doctrine.locations.values_list("pk", flat=True))


class EveFittingTag(models.Model):
    """Closed vocabulary of fitting tags (seeded from FittingTag choices)."""

    slug = models.SlugField(max_length=64, unique=True)
    label = models.CharField(max_length=64)

    class Meta:
        ordering = ["slug"]

    def __str__(self):
        return self.label


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

    # Stable app/guide catalog key (not versioned with EFT content).
    known_key = models.CharField(
        max_length=64,
        choices=KnownFitting.choices,
        blank=True,
        null=True,
        help_text="Optional system meaning, e.g. guide.fw-cruiser.omen-kite-pulse.",
    )

    # fitting info
    eft_format = models.TextField()
    latest_version = models.CharField(max_length=255, blank=True)

    minimum_pod = models.TextField(blank=True)
    recommended_pod = models.TextField(blank=True)
    pods = models.ManyToManyField(
        "EveFittingPod",
        blank=True,
        related_name="fittings",
    )
    tags = models.ManyToManyField(
        EveFittingTag,
        blank=True,
        related_name="fittings",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                condition=models.Q(deleted__isnull=True),
                name="unique_evefitting_name_not_deleted",
            ),
            models.UniqueConstraint(
                fields=["known_key"],
                condition=models.Q(deleted__isnull=True)
                & models.Q(known_key__isnull=False),
                name="unique_evefitting_known_key_not_deleted",
            ),
        ]

    def __str__(self):
        return str(self.name)

    @staticmethod
    def coerce_tags(raw):
        """Validate tags and return a sorted list of unique allowed slug values."""
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

    def tag_slugs(self) -> list[str]:
        """Sorted list of related EveFittingTag slugs."""
        if self.pk is None:
            return []
        return sorted(self.tags.values_list("slug", flat=True))

    def set_tag_slugs(self, raw, *, write_history: bool = True):
        """
        Replace M2M tags from a slug list. Optionally write history and bump
        latest_version when the slug set changes.
        """
        if self.pk is None:
            raise ValueError("Cannot set tags before the fitting is saved")
        coerced = self.coerce_tags(raw)
        current = self.tag_slugs()
        if coerced == current:
            return coerced

        if write_history and self.latest_version:
            old = (
                EveFitting.all_objects.filter(pk=self.pk)
                .values(
                    *EVE_FITTING_VERSIONED_SCALAR_FIELDS,
                    "latest_version",
                    "name",
                    "ship_id",
                )
                .first()
            )
            if old and old["latest_version"]:
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
                    tags=current,
                )
                new_version = str(uuid.uuid4())
                EveFitting.all_objects.filter(pk=self.pk).update(
                    latest_version=new_version
                )
                self.latest_version = new_version

        self.tags.set(
            [
                EveFittingTag.objects.get_or_create(
                    slug=slug,
                    defaults={
                        "label": dict(FittingTag.choices).get(slug, slug)
                    },
                )[0]
                for slug in coerced
            ]
        )
        return coerced

    def clean(self):
        super().clean()
        if self.known_key == "":
            self.known_key = None
        if self.known_key is not None:
            allowed = {c.value for c in KnownFitting}
            if self.known_key not in allowed:
                raise ValidationError(
                    {
                        "known_key": f"invalid known fitting key: {self.known_key!r}"
                    }
                )
            dupes = EveFitting.objects.filter(known_key=self.known_key)
            if self.pk:
                dupes = dupes.exclude(pk=self.pk)
            if dupes.exists():
                raise ValidationError(
                    {
                        "known_key": (
                            f"known key {self.known_key!r} is already assigned "
                            f"to another fitting."
                        )
                    }
                )

    def save(self, *args, **kwargs):
        if self.known_key == "":
            self.known_key = None
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = {*update_fields, "known_key"}

        derived_name = self.fitting_name_from_eft(self.eft_format)
        if derived_name and derived_name != self.name:
            self.name = derived_name
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = {*update_fields, "name"}

        if self.pk is None:
            if not self.latest_version:
                self.latest_version = str(uuid.uuid4())
        else:
            old = (
                EveFitting.all_objects.filter(pk=self.pk)
                .values(
                    *EVE_FITTING_VERSIONED_SCALAR_FIELDS,
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
                    for f in EVE_FITTING_VERSIONED_SCALAR_FIELDS
                )
                if versioned_changed:
                    if old["latest_version"]:
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
                            tags=self.tag_slugs(),
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


class EveFittingPod(MinmatarSoftDeleteModel):
    """Named implant loadout linked to ship fittings."""

    name = models.CharField(max_length=255)
    priority = models.PositiveSmallIntegerField(
        default=100,
        help_text="Lower numbers are higher precedence when multiple pods apply.",
    )
    description = models.TextField(blank=True, default="")
    pod_format = models.TextField(
        blank=True,
        default="",
        help_text="Newline-separated implant names.",
    )
    escape_frigate_fittings = models.ManyToManyField(
        EveFitting,
        blank=True,
        related_name="escape_pod_configs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "name"]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        invalid = [
            fitting.name
            for fitting in self.escape_frigate_fittings.all()
            if FittingTag.ESCAPE_FRIGATE not in fitting.tag_slugs()
        ]
        if invalid:
            raise ValidationError(
                "Escape frigate fittings must have the escape_frigate tag: "
                + ", ".join(invalid)
            )


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
        derived_name = EveFitting.fitting_name_from_eft(self.eft_format)
        if derived_name and derived_name != self.name:
            self.name = derived_name
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = {*update_fields, "name"}

        base_ship = EveFitting.ship_name_from_eft(self.base_fitting.eft_format)
        refit_ship = EveFitting.ship_name_from_eft(self.eft_format)
        if base_ship != refit_ship:
            raise ValidationError(
                f"Refit ship '{refit_ship}' must match base fitting ship '{base_ship}'"
            )
        super().save(*args, **kwargs)


class EveFittingModuleSubstitution(models.Model):
    """
    Per-fitting seeder fallback: if the preferred module cannot be sourced,
    buy/stock the substitute instead.
    """

    fitting = models.ForeignKey(
        EveFitting,
        on_delete=models.CASCADE,
        related_name="module_substitutions",
    )
    preferred_module = models.ForeignKey(
        EveType,
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name="If unavailable",
    )
    substitute_module = models.ForeignKey(
        EveType,
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name="Buy instead",
    )
    notes = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Optional context for seeders (e.g. why this swap is acceptable).",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["fitting", "preferred_module"],
                name="unique_fitting_preferred_module_substitution",
            ),
        ]
        ordering = ["preferred_module__name"]
        verbose_name = "module substitution"
        verbose_name_plural = "module substitutions"

    def __str__(self):
        preferred = (
            self.preferred_module.name if self.preferred_module_id else "?"
        )
        substitute = (
            self.substitute_module.name if self.substitute_module_id else "?"
        )
        return f"{preferred} → {substitute}"

    def clean(self):
        super().clean()
        if (
            self.preferred_module_id
            and self.substitute_module_id
            and self.preferred_module_id == self.substitute_module_id
        ):
            raise ValidationError(
                {
                    "substitute_module": (
                        "Substitute must be a different module than the preferred one."
                    )
                }
            )


class EveDoctrine(models.Model):
    """
    Model for storing doctrines
    """

    type_choices = (
        (DOCTRINE_TYPE_EXPERIMENTAL, "Experimental"),
        (DOCTRINE_TYPE_NON_STRATEGIC, "Non strategic"),
        (DOCTRINE_TYPE_STRATEGIC, "Strategic"),
    )
    name = models.CharField(max_length=255, unique=True)
    type = models.CharField(max_length=255, choices=type_choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    description = models.TextField()
    locations = models.ManyToManyField(EveLocation, blank=True)
    latest_version = models.CharField(max_length=255, blank=True)

    class Meta:
        permissions = [
            (
                "change_doctrine_non_strategic",
                "Can propose non strategic doctrine changes",
            ),
            (
                "approve_doctrine_non_strategic",
                "Can approve non strategic doctrine changes",
            ),
            (
                "change_doctrine_strategic",
                "Can propose strategic doctrine changes",
            ),
            (
                "approve_doctrine_strategic",
                "Can approve strategic doctrine changes",
            ),
            (
                "change_doctrine_fitting_non_strategic",
                "Can propose non strategic doctrine fitting changes",
            ),
            (
                "approve_doctrine_fitting_non_strategic",
                "Can approve non strategic doctrine fitting changes",
            ),
            (
                "change_doctrine_fitting_strategic",
                "Can propose strategic doctrine fitting changes",
            ),
            (
                "approve_doctrine_fitting_strategic",
                "Can approve doctrine fittings (strategic)",
            ),
        ]

    @property
    def doctrine_link(self):
        return f"https://my.minmatar.org/ships/doctrines/list/{self.id}"

    def __str__(self):
        return str(self.name)

    def save_without_versioning(self, *args, **kwargs):
        """Save without bumping latest_version / history (approval apply)."""
        self._skip_doctrine_versioning = True
        try:
            return super().save(*args, **kwargs)
        finally:
            if hasattr(self, "_skip_doctrine_versioning"):
                del self._skip_doctrine_versioning

    def save(self, *args, **kwargs):
        if getattr(self, "_skip_doctrine_versioning", False):
            super().save(*args, **kwargs)
            return

        if self.pk is None:
            if not self.latest_version:
                self.latest_version = str(uuid.uuid4())
        else:
            old = (
                EveDoctrine.objects.filter(pk=self.pk)
                .values(*EVE_DOCTRINE_VERSIONED_FIELDS, "latest_version")
                .first()
            )
            if old:
                scalar_changed = any(
                    not _eve_doctrine_scalar_equal(
                        f, old.get(f), getattr(self, f)
                    )
                    for f in EVE_DOCTRINE_VERSIONED_FIELDS
                )
                if scalar_changed and old["latest_version"]:
                    prior = EveDoctrine.objects.get(pk=self.pk)
                    EveDoctrineHistory.objects.create(
                        doctrine_id=self.pk,
                        superseded_version_id=old["latest_version"],
                        name=old["name"],
                        type=old["type"],
                        description=old["description"],
                        composition=composition_snapshot_for_doctrine(prior),
                        location_ids=location_ids_for_doctrine(prior),
                    )
                    self.latest_version = str(uuid.uuid4())

        super().save(*args, **kwargs)


class EveDoctrineHistory(models.Model):
    doctrine = models.ForeignKey(
        EveDoctrine,
        on_delete=models.CASCADE,
        related_name="version_history",
    )
    superseded_version_id = models.CharField(max_length=255, blank=True)
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=255)
    description = models.TextField()
    composition = models.JSONField(default=dict)
    location_ids = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        vid = self.superseded_version_id or "—"
        return f"{self.doctrine.name} ({vid[:8]})"


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


class ChangeRequestStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    CANCELLED = "cancelled", "Cancelled"


class EveDoctrineChangeRequest(models.Model):
    doctrine = models.ForeignKey(
        EveDoctrine,
        on_delete=models.CASCADE,
        related_name="change_requests",
    )
    status = models.CharField(
        max_length=32,
        choices=ChangeRequestStatus.choices,
        default=ChangeRequestStatus.PENDING,
    )
    tier = models.CharField(max_length=32)
    change_kind = models.CharField(max_length=64, default="full")
    payload = models.JSONField()
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="submitted_doctrine_change_requests",
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_doctrine_change_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.doctrine.name} ({self.status})"


class EveFittingChangeRequest(models.Model):
    fitting = models.ForeignKey(
        EveFitting,
        on_delete=models.CASCADE,
        related_name="change_requests",
    )
    refit = models.ForeignKey(
        EveFittingRefit,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="change_requests",
    )
    status = models.CharField(
        max_length=32,
        choices=ChangeRequestStatus.choices,
        default=ChangeRequestStatus.PENDING,
    )
    tier = models.CharField(max_length=32)
    change_kind = models.CharField(max_length=64)
    payload = models.JSONField()
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="submitted_fitting_change_requests",
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_fitting_change_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.fitting.name} ({self.status})"
