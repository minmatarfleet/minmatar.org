from django.db import models


class EsiContractFields(models.Model):
    """The ESI contract fields shared by character and corporation mirrors.

    Abstract, so each subclass keeps its own table. The subclass adds its
    owner foreign key and indexes. Field definitions here must match the
    migrations exactly (``makemigrations --check`` reports no changes).
    Fill them from an ESI row with ``eveonline.helpers.esi.esi_contract_defaults``.
    """

    contract_id = models.BigIntegerField(unique=True, primary_key=True)
    type = models.CharField(max_length=32, db_index=True)
    status = models.CharField(max_length=32, db_index=True)
    availability = models.CharField(max_length=32, blank=True)
    issuer_id = models.BigIntegerField()
    issuer_corporation_id = models.BigIntegerField(null=True, blank=True)
    assignee_id = models.BigIntegerField(null=True, blank=True)
    acceptor_id = models.BigIntegerField(null=True, blank=True)
    for_corporation = models.BooleanField(default=False)
    date_issued = models.DateTimeField(null=True, blank=True)
    date_expired = models.DateTimeField(null=True, blank=True)
    date_accepted = models.DateTimeField(null=True, blank=True)
    date_completed = models.DateTimeField(null=True, blank=True)
    days_to_complete = models.IntegerField(null=True, blank=True)
    price = models.DecimalField(
        max_digits=32, decimal_places=2, null=True, blank=True
    )
    reward = models.DecimalField(
        max_digits=32, decimal_places=2, null=True, blank=True
    )
    collateral = models.DecimalField(
        max_digits=32, decimal_places=2, null=True, blank=True
    )
    buyout = models.DecimalField(
        max_digits=32, decimal_places=2, null=True, blank=True
    )
    volume = models.DecimalField(
        max_digits=32, decimal_places=2, null=True, blank=True
    )
    start_location_id = models.BigIntegerField(null=True, blank=True)
    end_location_id = models.BigIntegerField(null=True, blank=True)
    title = models.CharField(blank=True, max_length=255)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
