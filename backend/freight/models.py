from django.db import models

from eveonline.models import EveCorporationContract, EveLocation

FREIGHT_CORPORATION_ID = 98705678
FREIGHT_CONTRACT_TYPE = "courier"


class FreightContractQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status__in=["outstanding", "in_progress"])

    def finished(self):
        return self.filter(status="finished")


class FreightContractManager(
    models.Manager.from_queryset(FreightContractQuerySet)
):
    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(
                type=FREIGHT_CONTRACT_TYPE,
                assignee_id=FREIGHT_CORPORATION_ID,
            )
        )


class FreightContract(EveCorporationContract):
    """Courier contracts assigned to MFL, regardless of which corp last synced the ESI row."""

    objects = FreightContractManager()

    class Meta:
        proxy = True


class EveFreightRoute(models.Model):
    """Model for a freight route. One direction only; set up the reverse as a separate route."""

    class RouteType(models.TextChoices):
        RATE = "rate", "Rate (ISK/m³ + collateral %)"
        FIXED = "fixed", "Fixed fee (max m³ + max collateral)"

    origin_location = models.ForeignKey(
        EveLocation,
        on_delete=models.CASCADE,
        related_name="origin_freight_routes",
        null=True,
    )
    destination_location = models.ForeignKey(
        EveLocation,
        on_delete=models.CASCADE,
        related_name="destination_freight_routes",
        null=True,
    )
    route_type = models.CharField(
        max_length=16,
        choices=RouteType.choices,
        default=RouteType.RATE,
        help_text=(
            "Rate: isk_per_m3 and collateral_modifier. "
            "Fixed: flat fee with max volume and max collateral."
        ),
    )
    isk_per_m3 = models.BigIntegerField(
        default=0,
        help_text="Flat ISK charged per m³ for this route (rate type only).",
    )
    collateral_modifier = models.FloatField(
        default=0,
        help_text=(
            "Optional: extra ISK per 1 ISK collateral "
            "(e.g. 0.01 = 1%% of collateral). Applies to both route types."
        ),
    )
    fixed_fee_millions = models.FloatField(
        default=0,
        help_text="Flat reward in millions of ISK (fixed type only).",
    )
    xl_fee_millions = models.FloatField(
        default=0,
        help_text=(
            "Extra flat reward in millions of ISK added when the contract "
            "volume exceeds 350,000 m³ (fixed type only)."
        ),
    )
    max_m3 = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum contract volume in m³ (fixed type).",
    )
    max_collateral = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Maximum collateral in ISK (fixed type).",
    )
    expiration_days = models.PositiveSmallIntegerField(
        default=3,
        help_text="Contract expiration time in days (how long the contract is available to accept).",
    )
    days_to_complete = models.PositiveSmallIntegerField(
        default=3,
        help_text="Days allowed to complete the contract after acceptance.",
    )
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
