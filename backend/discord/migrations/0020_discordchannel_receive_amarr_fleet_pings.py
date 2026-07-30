# Generated manually for Amarr fleet Discord channel flag

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("discord", "0019_discordchannel_receive_capital_pings"),
    ]

    operations = [
        migrations.AddField(
            model_name="discordchannel",
            name="receive_amarr_fleet_pings",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "When enabled, Amarr fleet_active feed events are posted here."
                ),
            ),
        ),
    ]
