from django.db import models


# Create your models here.
class EveFreightLocation(models.Model):
    """Model for a freight depot."""

    location_id = models.BigIntegerField(unique=True)
    name = models.CharField(max_length=255)
    short_name = models.CharField(max_length=32)

    def __str__(self):
        return self.name


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

    def __str__(self):
        return f"{self.orgin.short_name} -> {self.destination.short_name}"


class EveFreightRouteOption(models.Model):
    """Model for a freight route option."""

    route = models.ForeignKey(EveFreightRoute, on_delete=models.CASCADE)
    base_cost = models.BigIntegerField()
    collateral_modifier = models.FloatField()
    maximum_m3 = models.BigIntegerField()

    def __str__(self):
        return f"{self.route} ({self.maximum_m3} m3)"
