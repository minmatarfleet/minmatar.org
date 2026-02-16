from django.db import models

from fittings.models import EveFitting
from eveonline.models import EveLocation


class EveMarketContractExpectation(models.Model):
    fitting = models.ForeignKey(EveFitting, on_delete=models.CASCADE)
    location = models.ForeignKey(EveLocation, on_delete=models.RESTRICT)
    quantity = models.IntegerField(default=1)

    def __str__(self):
        return str(f"{self.fitting.name} - {self.location}")

    @property
    def current_quantity(self):
        return EveMarketContract.objects.filter(
            fitting=self.fitting,
            location=self.location,
            status="outstanding",
        ).count()

    @property
    def desired_quantity(self):
        return self.quantity

    @property
    def is_fulfilled(self):
        return self.current_quantity >= self.desired_quantity

    @property
    def is_understocked(self):
        understocked_percentage = 0.5
        return (
            self.current_quantity
            < self.desired_quantity * understocked_percentage
        )


class EveMarketContractResponsibility(models.Model):
    expectation = models.ForeignKey(
        EveMarketContractExpectation, on_delete=models.CASCADE
    )
    # character or corporation
    entity_id = models.BigIntegerField()

    def __str__(self):
        return str(
            f"{self.entity_id} - {self.expectation.fitting.name} - {self.expectation.location}"
        )


class EveMarketContract(models.Model):
    esi_contract_type = "item_exchange"
    tracked_statuses = ["outstanding", "finished"]
    status_choices = (
        ("outstanding", "Outstanding"),
        ("finished", "Finished"),
        ("expired", "Expired"),
    )
    id = models.BigIntegerField(unique=True, primary_key=True)
    status = models.CharField(max_length=255, choices=status_choices)
    title = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=32, decimal_places=2)
    assignee_id = models.BigIntegerField(null=True, blank=True)
    acceptor_id = models.BigIntegerField(null=True, blank=True)
    issuer_external_id = models.BigIntegerField()

    is_public = models.BooleanField(default=False)

    # audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_updated = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)

    # relationships
    location = models.ForeignKey(
        EveLocation, on_delete=models.RESTRICT, null=True, blank=True
    )
    fitting = models.ForeignKey(
        EveFitting, on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return str(f"{self.title} - {self.location}")


class EveMarketContractError(models.Model):
    title = models.CharField(max_length=255, db_index=True)
    quantity = models.IntegerField(default=1)
    issuer = models.ForeignKey(
        "eveonline.EveCharacter", on_delete=models.CASCADE
    )
    location = models.ForeignKey(
        EveLocation,
        on_delete=models.CASCADE,
    )
    updated_at = models.DateTimeField(auto_now=True)
