"""Repair landed prices that were pasted as line totals instead of unit prices.

Before the paste normaliser existed, a Multibuy-style paste
(``Name<TAB>qty<TAB>total``) stored the whole-line total as ``unit_price``,
so every per-hull contract price was inflated by the buy quantity. Uses the
same paste-wide vote as ``market.helpers.fitting_buy_prices`` against the
Jita reference recorded on each item.
"""

from decimal import Decimal

from django.db import migrations


def _rows_for_order(items):
    from market.helpers.fitting_buy_prices import PriceRow

    return [
        (
            item,
            PriceRow(
                price=Decimal(item.unit_price),
                buy_qty=int(item.buy_qty or 0),
                jita_unit=(
                    Decimal(item.jita_sell_min)
                    if item.jita_sell_min is not None
                    else None
                ),
            ),
        )
        for item in items
        if item.unit_price is not None
    ]


def forwards(apps, schema_editor):
    from market.helpers.fitting_buy_prices import (
        normalize_unit_price,
        pasted_prices_are_totals,
    )

    FittingBuyOrder = apps.get_model("market", "FittingBuyOrder")
    FittingBuyOrderItem = apps.get_model("market", "FittingBuyOrderItem")
    for order in FittingBuyOrder.objects.all().iterator():
        rows = _rows_for_order(
            FittingBuyOrderItem.objects.filter(order_id=order.pk)
        )
        if not rows:
            continue
        if not pasted_prices_are_totals([price for _, price in rows]):
            continue
        for item, price in rows:
            fixed = normalize_unit_price(price, totals=True)
            if fixed != item.unit_price:
                item.unit_price = fixed
                item.save(update_fields=["unit_price"])


class Migration(migrations.Migration):
    dependencies = [
        ("market", "0050_fittingbuyorder_contract_markup"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
