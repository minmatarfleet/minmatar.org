from django.db import models
from eveuniverse.models import EveType

from fittings.models import EveFitting
from structures.models import EveStructure


class EveMarketContractExpectation(models.Model):
    """Model for seeding a quantity of fittings"""

    fitting = models.ForeignKey(EveFitting, on_delete=models.CASCADE)
    location = models.ForeignKey(EveStructure, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)

    def __str__(self):
        return str(f"{self.fitting.name} - {self.location.name}")


class EveMarketContractResponsibility(models.Model):
    """Model for tracking who is responsible for a fitting"""

    expectation = models.ForeignKey(
        EveMarketContractExpectation, on_delete=models.CASCADE
    )
    # character or corporation
    entity_id = models.BigIntegerField()

    def __str__(self):
        return str(
            f"{self.character.character_name} - {self.fitting.fitting.name}"
        )


class EveMarketContract(models.Model):
    """
    Model for tracking market contracts
    """

    contract_id = models.BigIntegerField(unique=True)
    status = models.CharField(
        max_length=32,
        choices=(("outstanding", "Outstanding"), ("completed", "Completed")),
    )
    title = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=32, decimal_places=2)
    assignee_id = models.BigIntegerField(null=True, blank=True)
    acceptor_id = models.BigIntegerField(null=True, blank=True)
    issuer_external_id = models.BigIntegerField()

    # audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # relationships
    fitting = models.ForeignKey(
        EveFitting, on_delete=models.SET_NULL, null=True, blank=True
    )


class EveMarketItemExpectation(models.Model):
    """Model for seeding a quantity of items"""

    item = models.ForeignKey(EveType, on_delete=models.CASCADE)
    location = models.ForeignKey(EveStructure, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)

    def __str__(self):
        return str(f"{self.item.name} - {self.location.name}")


class EveMarketItemResponsibility(models.Model):
    """Model for tracking who is responsible for an item"""

    expectation = models.ForeignKey(
        EveMarketItemExpectation, on_delete=models.CASCADE
    )
    # character or corporation
    entity_id = models.BigIntegerField()

    def __str__(self):
        return str(f"{self.character.character_name} - {self.item.name}")


class EveMarketItemOrder(models.Model):
    """Model for tracking an order for an item"""

    item = models.ForeignKey(EveType, on_delete=models.CASCADE)
    location = models.ForeignKey(EveStructure, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=32, decimal_places=2)
    quantity = models.IntegerField()
    issuer_external_id = models.BigIntegerField()

    def __str__(self):
        return str(f"{self.item.name} - {self.location.name}")


class EveMarketItemTransaction(models.Model):
    """Model for tracking a transaction for an item"""

    item = models.ForeignKey(EveType, on_delete=models.CASCADE)
    location = models.ForeignKey(EveStructure, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=32, decimal_places=2)
    quantity = models.IntegerField()
    issuer_external_id = models.BigIntegerField()
    sell_date = models.DateTimeField()

    def __str__(self):
        return str(f"{self.item.name} - {self.location.name}")
