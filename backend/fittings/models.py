import uuid

from django.core.exceptions import ValidationError
from django.db import models

from groups.models import Sig

# Create your models here.


class EveFittingTag(models.Model):
    """
    Model for storing tags for fittings
    """

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField()

    def __str__(self):
        return str(self.name)


class EveFitting(models.Model):
    """
    Model for storing fittings
    """

    name = models.CharField(max_length=255, unique=True)
    ship_id = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    description = models.TextField()
    tags = models.ManyToManyField(EveFittingTag, blank=True)
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
        fitting_name = self.eft_format.split("\n")[0].split(",")[1].strip()
        fitting_name = fitting_name[:-1].strip()
        if self.name != fitting_name:
            raise ValidationError(
                f"Name '{self.name}' does not match EFT name '{fitting_name}'"
            )
        super().save(*args, **kwargs)


class EveDoctrine(models.Model):
    """
    Model for storing doctrines
    """

    type_choices = (
        ("skirmish", "Skirmish"),
        ("strategic", "Strategic"),
        ("specialized", "Specialized"),
        ("casual", "Casual"),
        ("faction_warfare", "Faction warfare"),
        ("nullsec", "Nullsec"),
    )
    name = models.CharField(max_length=255, unique=True)
    type = models.CharField(max_length=255, choices=type_choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    description = models.TextField()
    sigs = models.ManyToManyField(Sig, blank=True)
    ideal_fleet_size = models.IntegerField(default=50)

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
    ideal_ship_count = models.IntegerField(default=1)

    def __str__(self):
        return f"{self.doctrine.name} - {self.fitting.name}"
