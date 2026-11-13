from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("buyback", "0012_pause_water"),
    ]

    operations = [
        migrations.AddField(
            model_name="buybackpurchaseorder",
            name="settlement_step",
            field=models.CharField(
                choices=[
                    ("contract_up", "Contract up"),
                    ("awaiting_accept", "Awaiting accept"),
                ],
                default="contract_up",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="buybackpurchaseorder",
            name="team_prompted",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="evebuybacksettings",
            name="coordinators",
            field=models.ManyToManyField(
                blank=True,
                help_text=(
                    "Users who can see pending hangar sales, mark the "
                    "Discord contract up, and complete or cancel sales."
                ),
                related_name="buyback_coordinator_settings",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
