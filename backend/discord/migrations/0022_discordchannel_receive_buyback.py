# Generated manually for hangar buyback Discord channel flag

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("discord", "0021_discordchannel_receive_lp_buyback"),
    ]

    operations = [
        migrations.AddField(
            model_name="discordchannel",
            name="receive_buyback",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "When enabled, hangar buyback purchase-order threads are "
                    "created in this forum. Only one channel should have this "
                    "enabled."
                ),
            ),
        ),
    ]
