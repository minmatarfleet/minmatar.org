from django.db import models

from eveuniverse.models import EveType
from eveonline.models import EveLocation


class EveMarketItemExpectation(models.Model):
    item = models.ForeignKey(EveType, on_delete=models.CASCADE)
    location = models.ForeignKey(EveLocation, on_delete=models.RESTRICT)
    quantity = models.IntegerField(default=1)

    def __str__(self):
        return str(f"{self.item.name} - {self.location.name}")


class EveMarketItemResponsibility(models.Model):
    expectation = models.ForeignKey(
        EveMarketItemExpectation, on_delete=models.CASCADE
    )
    # character or corporation
    entity_id = models.BigIntegerField()

    def __str__(self):
        return str(f"{self.entity_id} - {self.expectation.item.name}")


class EveMarketItemOrder(models.Model):
    item = models.ForeignKey(EveType, on_delete=models.CASCADE)
    location = models.ForeignKey(EveLocation, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=32, decimal_places=2)
    quantity = models.IntegerField()
    issuer_external_id = models.BigIntegerField()

    def __str__(self):
        return str(f"{self.item.name} - {self.location.name}")


class EveMarketItemTransaction(models.Model):
    item = models.ForeignKey(EveType, on_delete=models.CASCADE)
    location = models.ForeignKey(EveLocation, on_delete=models.RESTRICT)
    price = models.DecimalField(max_digits=32, decimal_places=2)
    quantity = models.IntegerField()
    issuer_external_id = models.BigIntegerField()
    sell_date = models.DateTimeField()

    def __str__(self):
        return str(f"{self.item.name} - {self.location.name}")
