from django.db import migrations, models

# Fitting order 46 is 11x Revelation. Industry order 44 (3Rh) is the
# fulfilled Revelation ask at 2.1B those hulls came from.
_FITTING_ORDER_ID = 46
_HULL_TYPE_ID = 19720
_INDUSTRY_ORDER_ID = 44


def pin_order_46_revelation(apps, schema_editor):
    FittingBuyOrder = apps.get_model("market", "FittingBuyOrder")
    IndustryOrderItem = apps.get_model("industry", "IndustryOrderItem")
    order = FittingBuyOrder.objects.filter(pk=_FITTING_ORDER_ID).first()
    if order is None:
        return
    if not IndustryOrderItem.objects.filter(
        order_id=_INDUSTRY_ORDER_ID,
        eve_type_id=_HULL_TYPE_ID,
    ).exists():
        return
    sources = dict(order.hull_industry_sources or {})
    sources[str(_HULL_TYPE_ID)] = _INDUSTRY_ORDER_ID
    order.hull_industry_sources = sources
    order.save(update_fields=["hull_industry_sources"])


def unpin_order_46_revelation(apps, schema_editor):
    FittingBuyOrder = apps.get_model("market", "FittingBuyOrder")
    order = FittingBuyOrder.objects.filter(pk=_FITTING_ORDER_ID).first()
    if order is None:
        return
    sources = dict(order.hull_industry_sources or {})
    if sources.get(str(_HULL_TYPE_ID)) != _INDUSTRY_ORDER_ID:
        return
    sources.pop(str(_HULL_TYPE_ID), None)
    order.hull_industry_sources = sources
    order.save(update_fields=["hull_industry_sources"])


class Migration(migrations.Migration):
    dependencies = [
        ("market", "0051_fittingbuyorderitem_normalize_pasted_totals"),
    ]

    operations = [
        migrations.AddField(
            model_name="fittingbuyorder",
            name="hull_industry_sources",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    "Hull price source when no open industry ask exists: "
                    '{ "<ship_type_id>": <industry_order_id> } or 0 to use Jita.'
                ),
            ),
        ),
        migrations.RunPython(
            pin_order_46_revelation,
            unpin_order_46_revelation,
        ),
    ]
