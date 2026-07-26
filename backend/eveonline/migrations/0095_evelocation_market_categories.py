from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("eveonline", "0094_evecharacter_security_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="evelocation",
            name="market_categories",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Fitting tags that qualify sell-order fittings at this location (ANY match).",
            ),
        ),
    ]
