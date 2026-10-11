from django.db import migrations, models


def forwards_null_unfinished_stock(apps, schema_editor):
    """Draft orders that never left the stock step keep stock_paste null."""
    FittingBuyOrder = apps.get_model("market", "FittingBuyOrder")
    FittingBuyOrder.objects.filter(status="draft", stock_paste="").update(
        stock_paste=None
    )


class Migration(migrations.Migration):
    dependencies = [
        ("market", "0047_fittingbuyorderline_swap_hull_qty"),
    ]

    operations = [
        migrations.AlterField(
            model_name="fittingbuyorder",
            name="stock_paste",
            field=models.TextField(
                blank=True,
                default=None,
                help_text=(
                    "Raw inventory / Multibuy paste applied against the BOM. "
                    "Null means the on-hand stock step is not done yet; empty "
                    "string means the owner skipped or cleared stock."
                ),
                null=True,
            ),
        ),
        migrations.RunPython(
            forwards_null_unfinished_stock, migrations.RunPython.noop
        ),
    ]
