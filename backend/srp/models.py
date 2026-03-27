from django.contrib.auth.models import User
from django.db import models
from eveuniverse.models import EveType

from fleets.models import EveFleet
from combatlog.models import CombatLog


class EveFleetShipReimbursement(models.Model):
    """
    Represents a SRP request
    """

    status_choices = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("withdrawn", "Withdrawn"),
    )
    category_choices = (
        ("logistics", "Logistics"),
        ("support", "Support"),
        ("dps", "DPS"),
        ("capital", "Capital"),
        ("other", "Other"),
    )
    fleet = models.ForeignKey(
        EveFleet,
        on_delete=models.CASCADE,
        related_name="reimbursements",
        null=True,
    )
    external_killmail_link = models.CharField(max_length=255)
    status = models.CharField(
        max_length=32, choices=status_choices, default="pending"
    )
    category = models.CharField(
        max_length=32, choices=category_choices, null=True
    )

    # populated fields
    killmail_id = models.BigIntegerField(db_index=True)
    character_id = models.BigIntegerField()
    character_name = models.CharField(max_length=255)
    primary_character_id = models.BigIntegerField()
    primary_character_name = models.CharField(max_length=255)
    amount = models.BigIntegerField()
    reimbursement_program_amount = models.ForeignKey(
        "ShipReimbursementProgramAmount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    ship_name = models.CharField(max_length=255)
    ship_type_id = models.BigIntegerField()
    is_corp_ship = models.BooleanField(default=False)
    corp_id = models.BigIntegerField(null=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    comments = models.CharField(max_length=255, null=True)
    combat_log = models.ForeignKey(
        CombatLog, on_delete=models.SET_NULL, null=True
    )

    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "fleet", "user"]),
        ]


class ShipReimbursementProgram(models.Model):
    """
    A reimbursement program for one EVE type.
    """

    eve_type = models.ForeignKey(
        EveType,
        on_delete=models.CASCADE,
        related_name="srp_reimbursement_programs",
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)


class ShipReimbursementProgramAmount(models.Model):
    """
    Time series of reimbursement amounts for one program.
    """

    program = models.ForeignKey(
        ShipReimbursementProgram,
        on_delete=models.CASCADE,
        related_name="amounts",
    )
    srp_value = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
