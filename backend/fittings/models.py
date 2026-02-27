import uuid

from django.core.exceptions import ValidationError
from django.db import models

from eveonline.models import EveLocation
from groups.models import Sig

# Create your models here.


class EveFitting(models.Model):
    """
    Model for storing fittings
    """

    name = models.CharField(max_length=255, unique=True)
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

    def __str__(self):
        return str(self.name)

    def save(self, *args, **kwargs):
        self.latest_version = str(uuid.uuid4())
        fitting_name = self.fitting_name_from_eft(self.eft_format)
        if self.name != fitting_name:
            raise ValidationError(
                f"Name '{self.name}' does not match EFT name '{fitting_name}'"
            )
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
    sigs = models.ManyToManyField(Sig, blank=True)
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
