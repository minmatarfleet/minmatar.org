from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("market", "0046_fitting_buy_allocations"),
    ]

    operations = [
        migrations.AddField(
            model_name="fittingbuyorderline",
            name="swap_hull_qty",
            field=models.PositiveIntegerField(
                blank=True,
                help_text=(
                    "When set with swaps, this many hulls use the swapped EFT; "
                    "the rest keep the original fit. Null means all hulls are swapped."
                ),
                null=True,
            ),
        ),
    ]
