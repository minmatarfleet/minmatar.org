from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("market", "0049_fittingbuyorder_status_completed"),
    ]

    operations = [
        migrations.AddField(
            model_name="fittingbuyorder",
            name="contract_markup_pct",
            field=models.DecimalField(
                decimal_places=1,
                default=20,
                help_text=(
                    "Markup over landed cost used for recommended contract "
                    "prices."
                ),
                max_digits=5,
            ),
        ),
        migrations.AddField(
            model_name="fittingbuyorder",
            name="contract_type",
            field=models.CharField(
                choices=[
                    ("alliance", "Alliance contract"),
                    ("public", "Public contract"),
                ],
                default="alliance",
                help_text=(
                    "Contract availability; public contracts pay a broker fee."
                ),
                max_length=16,
            ),
        ),
    ]
