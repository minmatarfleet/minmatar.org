# Generated manually for LP buyback Discord channel flag

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("discord", "0020_discordchannel_receive_amarr_fleet_pings"),
    ]

    operations = [
        migrations.AddField(
            model_name="discordchannel",
            name="receive_lp_buyback",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "When enabled, LP buyback order threads are created in "
                    "this forum. Only one channel should have this enabled."
                ),
            ),
        ),
    ]
