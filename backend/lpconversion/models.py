from django.core.cache import cache
from django.db import models
from django.contrib.auth.models import User

lp_type_ids = [
    41490,
    32006,
    32014,
    21894,
    21896,
    21898,
    21902,
    21904,
    21906,
    21918,
    21922,
    21924,
    31932,
    31928,
    31924,
    31944,
    41212,
    41215,
    41218,
    33157,
    29336,
    17713,
    72811,
    31890,
    31888,
    31892,
    31894,
    15939,
]

lp_blueprint_ids = {
    # Item: Blueprint
    33157: 33158,
    72811: 72923,
    29336: 29339,
    17713: 17714,
}


class LpSellOrder(models.Model):
    """
    A request to sell loyalty points.
    """

    status_choices = (
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("sent", "LP Sent"),
        ("paid", "Paid"),
        ("closed", "Closed"),
    )
    status = models.CharField(
        max_length=10, choices=status_choices, default="pending"
    )
    seller = models.ForeignKey(User, on_delete=models.CASCADE)
    loyalty_points = models.IntegerField(default=0)
    rate = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    discord_thread_id = models.BigIntegerField(blank=True, null=True)


class LpBuyOffer(models.Model):
    """
    An offer to buy loyalty points, linked to an order.
    """

    buyer = models.ForeignKey(User, on_delete=models.CASCADE)
    order = models.ForeignKey(LpSellOrder, on_delete=models.CASCADE)
    loyalty_points = models.IntegerField(default=0)
    rate = models.IntegerField(default=0)
    corporation = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class LpStoreItem(models.Model):
    """
    Model for loyalty point store items.
    """

    type_id = models.IntegerField(
        primary_key=True, serialize=True, auto_created=False
    )
    description = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)
    qty_1d = models.IntegerField(default=0)
    qty_7d = models.IntegerField(default=0)
    qty_30d = models.IntegerField(default=0)
    blueprint_id = models.IntegerField(null=True)
    store_qty = models.IntegerField(default=0)
    store_lp = models.IntegerField(default=0)
    store_isk = models.IntegerField(default=0)
    jita_price = models.DecimalField(
        default=0.0, max_digits=15, decimal_places=2
    )

    def __str__(self):
        return str(self.type_id) + ": " + str(self.description)


def set_status(status):
    cache.set("lpconvert_status", status)


def get_status():
    status = cache.get("lpconvert_status")
    if status is None:
        return "Unknown"
    return status


def update_lp_item(
    type_id,
    description,
    qty_1d,
    qty_7d,
    qty_30d,
    store_qty,
    store_lp,
    store_isk,
    price,
):
    try:
        lp_item = LpStoreItem.objects.get(type_id=type_id)
    except LpStoreItem.DoesNotExist:
        lp_item = LpStoreItem(type_id=type_id)

    lp_item.description = description
    lp_item.qty_1d = qty_1d
    lp_item.qty_7d = qty_7d
    lp_item.qty_30d = qty_30d

    lp_item.store_qty = store_qty
    lp_item.store_lp = store_lp
    lp_item.store_isk = store_isk

    lp_item.jita_price = price

    lp_item.save()
