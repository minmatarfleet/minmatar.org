from django.db import models


# Create your models here.
class EveFreightLocation(models.Model):
    """Model for a freight depot."""

    location_id = models.BigIntegerField(unique=True)
    name = models.CharField(max_length=255)
    short_name = models.CharField(max_length=32)


class EveFreightRoute(models.Model):
    """Model for a freight route."""

    orgin = models.ForeignKey(
        EveFreightLocation, on_delete=models.CASCADE, related_name="orgin"
    )
    destination = models.ForeignKey(
        EveFreightLocation,
        on_delete=models.CASCADE,
        related_name="destination",
    )
    bidirectional = models.BooleanField(default=True)


class EveFreightRouteOption(models.Model):
    """Model for a freight route option."""

    route = models.ForeignKey(EveFreightRoute, on_delete=models.CASCADE)
    base_cost = models.BigIntegerField()
    collateral_modifier = models.FloatField()
    maximum_m3 = models.BigIntegerField()
