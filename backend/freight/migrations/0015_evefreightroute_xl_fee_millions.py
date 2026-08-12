from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("freight", "0014_fixed_cost_route_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="evefreightroute",
            name="xl_fee_millions",
            field=models.FloatField(
                default=0,
                help_text="Extra flat reward in millions of ISK added when the contract volume exceeds 350,000 m³ (fixed type only).",
            ),
        ),
        migrations.AlterField(
            model_name="evefreightroute",
            name="collateral_modifier",
            field=models.FloatField(
                default=0,
                help_text="Optional: extra ISK per 1 ISK collateral (e.g. 0.01 = 1%% of collateral). Applies to both route types.",
            ),
        ),
    ]
