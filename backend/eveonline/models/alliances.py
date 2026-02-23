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
    market_active = models.BooleanField(default=False)
    prices_active = models.BooleanField(default=False)
    freight_active = models.BooleanField(default=False)
    staging_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return str(self.location_name)
