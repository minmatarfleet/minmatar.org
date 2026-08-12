from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("market", "0045_remove_fittingbuyorderline_effective_eft"),
    ]

    operations = [
        migrations.AddField(
            model_name="fittingbuyorder",
            name="shopping_allocations",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    "Buy splits for short types: "
                    '{ "<preferred_type_id>": [{"type_id": int, "qty": int}, ...] }.'
                ),
            ),
        ),
        migrations.AddField(
            model_name="fittingbuyorder",
            name="variant_jita_cache",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    "Jita depth for short-item variants from the last check: "
                    '{ "<type_id>": {"volume", "order_count", "sell_min"} }.'
                ),
            ),
        ),
    ]
