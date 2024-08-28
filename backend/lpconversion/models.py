from django.core.cache import cache

from django.db import models

lp_type_ids = [
    # 41490,
    # 32006,
    # 32014,
    # 21894,
    # 21896,
    # 21898,
    # 21902,
    # 21904,
    # 21906,
    # 21918,
    # 21922,
    # 21924,
    # 31932,
    # 31928,
    # 31924,
    # 31944,
    # 41212,
    # 41215,
    41218,
    # 33157,
    # 29336,
    # 17713,
    # 72811,
    31890,
    31888,
    31892,
    31894,
]

lp_blueprint_ids = {
    # Blueprint: Item
    33158: 33157,
    72923: 72811,
    29339: 29336,
    17714: 17713,
}


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

    def __str__(self):
        return str(self.type_id) + ": " + str(self.description)


def set_status(status):
    cache.set("lpconvert_status", status)


def get_status():
    status = cache.get("lpconvert_status")
    if status is None:
        return "Unknown"
    return status


def update_lp_item(type_id, description, qty_1d, qty_7d, qty_30d):
    try:
        lp_item = LpStoreItem.objects.get(type_id=type_id)
    except LpStoreItem.DoesNotExist:
        lp_item = LpStoreItem(type_id=type_id)

    lp_item.description = description
    lp_item.qty_1d = qty_1d
    lp_item.qty_7d = qty_7d
    lp_item.qty_30d = qty_30d

    lp_item.save()
