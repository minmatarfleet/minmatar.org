from django.db import models

from eveonline.models import EveLocation


# Create your models here.
class EveFreightContract(models.Model):
    """Model for a freight contract."""

    expected_contract_type = "courier"
    supported_ceo_id = 96046515
    supported_corporation_id = 98705678

    tracked_statuses = ["outstanding", "in_progress", "finished"]
    status_choices = (
        ("outstanding", "Outstanding"),
        ("in_progress", "In Progress"),
        ("finished", "Finished"),
        ("expired", "Expired"),
    )

    contract_id = models.BigIntegerField(unique=True)
    status = models.CharField(max_length=32)
    start_location_name = models.CharField(max_length=255)
    end_location_name = models.CharField(max_length=255)
    volume = models.BigIntegerField()
    collateral = models.BigIntegerField()
    reward = models.BigIntegerField()
    date_issued = models.DateTimeField()
    date_completed = models.DateTimeField(null=True, blank=True)
    issuer = models.ForeignKey(
        "eveonline.EveCharacter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="issued_freight_contracts",
    )
    completed_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completed_contracts",
    )

    def __str__(self):
        return f"{self.contract_id} ({self.status})"


class EveFreightRoute(models.Model):
    """Model for a freight route."""

    origin_location = models.ForeignKey(
        EveLocation,
        on_delete=models.CASCADE,
        related_name="origin_location",
        null=True,
    )
    destination_location = models.ForeignKey(
        EveLocation,
        on_delete=models.CASCADE,
        related_name="destination_location",
        null=True,
    )
    bidirectional = models.BooleanField(default=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        origin_name = (
            self.origin_location.short_name
            if self.origin_location
            else "Unknown"
        )
        dest_name = (
            self.destination_location.short_name
            if self.destination_location
            else "Unknown"
        )
        return f"{origin_name} -> {dest_name}"


class EveFreightRouteOption(models.Model):
    """Model for a freight route option."""

    route = models.ForeignKey(EveFreightRoute, on_delete=models.CASCADE)
    base_cost = models.BigIntegerField()
    collateral_modifier = models.FloatField()
    maximum_m3 = models.BigIntegerField()

    def __str__(self):
        return f"{self.route} ({self.maximum_m3} m3)"
