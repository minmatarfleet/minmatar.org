from django.db import models

from fleets.models import EveFleet


# Create your models here.
class EveFleetShipReimbursement(models.Model):
    """
    Represents a SRP request
    """

    status_choices = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )
    fleet = models.ForeignKey(
        EveFleet, on_delete=models.CASCADE, related_name="reimbursements"
    )
    external_killmail_link = models.CharField(max_length=255)
    status = models.CharField(
        max_length=32, choices=status_choices, default="pending"
    )

    # populated
    killmail_id = models.BigIntegerField()
    character_id = models.BigIntegerField()
    primary_character_id = models.BigIntegerField()
    amount = models.BigIntegerField()
    ship_name = models.CharField(max_length=255)
