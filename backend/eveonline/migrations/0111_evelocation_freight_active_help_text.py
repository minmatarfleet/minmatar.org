from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("eveonline", "0110_corporation_discord_bot"),
    ]

    operations = [
        migrations.AlterField(
            model_name="evelocation",
            name="freight_active",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Turning this off also disables freight routes "
                    "to and from this location."
                ),
            ),
        ),
    ]
