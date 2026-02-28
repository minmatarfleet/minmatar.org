from django.core.exceptions import ValidationError
from django.db import models


class EveAlliance(models.Model):
    """Alliance model"""

    alliance_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=255, blank=True)
    ticker = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        indexes = [models.Index(fields=["name"])]

    def __str__(self):
        return str(self.name)


class EveLocation(models.Model):
    """An alliance location for freight, market or staging"""

    location_id = models.BigIntegerField(primary_key=True)
    location_name = models.CharField(max_length=255)
    solar_system_id = models.BigIntegerField()
    solar_system_name = models.CharField(max_length=255)
    short_name = models.CharField(max_length=32)
    region_id = models.BigIntegerField(null=True)
    is_structure = models.BooleanField(
        default=False,
        help_text="True if location_id is an Upwell structure (use structure markets API). False for NPC station (use region orders API).",
    )
    market_active = models.BooleanField(default=False)
    prices_active = models.BooleanField(default=False)
    price_baseline = models.BooleanField(
        default=False,
        help_text="At most one location may be the price baseline. "
        "Used as the reference for markup calculations.",
    )
    freight_active = models.BooleanField(default=False)
    staging_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["price_baseline"],
                condition=models.Q(price_baseline=True),
                name="unique_price_baseline_location",
            ),
        ]

    def clean(self):
        if self.price_baseline:
            dup = (
                EveLocation.objects.filter(price_baseline=True)
                .exclude(pk=self.pk)
                .first()
            )
            if dup:
                raise ValidationError(
                    f"Only one location can be the price baseline. "
                    f'"{dup.location_name}" already has it enabled.'
                )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return str(self.location_name)
